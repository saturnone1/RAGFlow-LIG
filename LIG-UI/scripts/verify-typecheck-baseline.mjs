import { readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const [mode, baselinePath] = process.argv.slice(2);
if (!['snapshot', 'check'].includes(mode) || !baselinePath) {
  throw new Error('usage: verify-typecheck-baseline.mjs <snapshot|check> <baseline.json>');
}

const result = spawnSync('npm', ['run', 'type-check'], {
  encoding: 'utf8',
  maxBuffer: 32 * 1024 * 1024,
});
const output = `${result.stdout ?? ''}\n${result.stderr ?? ''}`;
const errors = [...output.matchAll(/^(src\/[^(\r\n]+)(?:\(\d+,\d+\))?: error (TS\d+): (.+)$/gm)]
  .map((match) => `${match[1]}|${match[2]}|${match[3]}`)
  .sort();

if (mode === 'snapshot') {
  writeFileSync(baselinePath, `${JSON.stringify(errors, null, 2)}\n`);
  console.log(`Recorded ${errors.length} upstream TypeScript errors as the v0.26.4 baseline.`);
  process.exit(0);
}

const baseline = new Set(JSON.parse(readFileSync(baselinePath, 'utf8')));
const regressions = [...new Set(errors)].filter((error) => !baseline.has(error));
if (regressions.length > 0) {
  console.error('The LIG overlay introduced new TypeScript errors:');
  for (const error of regressions) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`TypeScript regression gate passed (${errors.length} current, ${baseline.size} upstream baseline).`);
