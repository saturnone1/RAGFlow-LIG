{{- define "lig-ragflow.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "lig-ragflow.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lig-ragflow.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lig-ragflow.labels" -}}
app.kubernetes.io/name: {{ include "lig-ragflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "lig-ragflow.selector" -}}
app.kubernetes.io/name: {{ include "lig-ragflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lig-ragflow.secret" -}}
{{- required "secret.existingSecret is required" .Values.secret.existingSecret -}}
{{- end -}}

{{- define "lig-ragflow.storageClass" -}}
{{- with .Values.global.storageClass }}storageClassName: {{ . | quote }}{{- end }}
{{- end -}}

{{- define "lig-ragflow.pullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

