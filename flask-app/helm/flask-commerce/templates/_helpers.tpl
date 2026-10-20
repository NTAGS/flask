{{- define "flask-commerce.name" -}}flask-commerce{{- end }}
{{- define "flask-commerce.fullname" -}}{{ include "flask-commerce.name" . }}{{- end }}
{{- define "flask-commerce.secretName" -}}{{- if .Values.secret.existingSecret -}}{{ .Values.secret.existingSecret }}{{- else -}}{{ include "flask-commerce.fullname" . }}-secret{{- end -}}{{- end }}
{{- define "flask-commerce.labels" -}}app.kubernetes.io/name: {{ include "flask-commerce.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}{{- end }}
