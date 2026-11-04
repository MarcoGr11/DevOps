{{/* Chart name, overridable */}}
{{- define "booking.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Full name: <release>-<chart>, or just <release> if it already contains the chart name.
All object names are built from it, so two releases never collide.
*/}}
{{- define "booking.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := include "booking.name" . }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "booking.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Selector labels; usage: include "booking.selectorLabels" (dict "ctx" $ "component" "api") */}}
{{- define "booking.selectorLabels" -}}
app.kubernetes.io/name: {{ include "booking.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
{{- with .component }}
app.kubernetes.io/component: {{ . }}
{{- end }}
{{- end }}

{{/* Common labels; same arguments as selectorLabels, component optional */}}
{{- define "booking.labels" -}}
helm.sh/chart: {{ include "booking.chart" .ctx }}
{{ include "booking.selectorLabels" . }}
app.kubernetes.io/version: {{ .ctx.Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .ctx.Release.Service }}
app.kubernetes.io/part-of: {{ include "booking.name" .ctx }}
{{- end }}

{{/* Image reference; usage: include "booking.image" (dict "ctx" $ "image" .Values.image.api) */}}
{{- define "booking.image" -}}
{{- printf "%s:%s" .image.repository (.image.tag | default .ctx.Chart.AppVersion | toString) }}
{{- end }}

{{- define "booking.postgresHost" -}}
{{- printf "%s-postgres" (include "booking.fullname" .) }}
{{- end }}
