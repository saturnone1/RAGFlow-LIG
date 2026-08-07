#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os

from common.asyncio_utils import LoopLocalSemaphore

MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", "5"))
MAX_CONCURRENT_CHUNK_BUILDERS = int(os.environ.get("MAX_CONCURRENT_CHUNK_BUILDERS", "1"))
MAX_CONCURRENT_MINIO = int(os.environ.get("MAX_CONCURRENT_MINIO", "10"))
# Parser concurrency and embedding concurrency pull in opposite directions: the
# first divides the memory budget for page batching, the second decides how many
# requests the embedding backend can group into one forward pass. Defaulting to
# the parser value keeps the previous behaviour when this is not set.
MAX_CONCURRENT_EMBEDDERS = int(os.environ.get("MAX_CONCURRENT_EMBEDDERS", str(MAX_CONCURRENT_CHUNK_BUILDERS)))

task_limiter = LoopLocalSemaphore(MAX_CONCURRENT_TASKS)
chunk_limiter = LoopLocalSemaphore(MAX_CONCURRENT_CHUNK_BUILDERS)
embed_limiter = LoopLocalSemaphore(MAX_CONCURRENT_EMBEDDERS)
minio_limiter = LoopLocalSemaphore(MAX_CONCURRENT_MINIO)
kg_limiter = LoopLocalSemaphore(2)
