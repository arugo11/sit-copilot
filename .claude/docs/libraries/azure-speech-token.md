# Azure Speech Token Issuance Notes

Generated: 2026-02-20

## Official References

- Azure AI services authentication:
  - https://learn.microsoft.com/en-us/azure/ai-services/authentication
- Speech SDK JS `SpeechConfig` reference:
  - https://learn.microsoft.com/en-us/javascript/api/microsoft-cognitiveservices-speech-sdk/speechconfig

## Key Facts

1. STS issue-token endpoint
- `POST https://<region>.api.cognitive.microsoft.com/sts/v1.0/issueToken`
- header: `Ocp-Apim-Subscription-Key: <speech-key>`
- body: empty

2. Token lifetime
- issued access token is valid for 10 minutes (600 seconds).

3. Speech SDK usage
- browser/client apps use `SpeechConfig.fromAuthorizationToken(token, region)`.
- token must be refreshed before expiry.
- updating token on `SpeechConfig` does not automatically refresh already-created recognizers/synthesizers.

## Practical Guidance for This Repo

- backend endpoint should return a conservative `expires_in_sec` (e.g., 540) to encourage pre-expiry refresh.
- keep subscription key server-side only; frontend receives only short-lived token + region.
- map upstream STS failures to deterministic API error and avoid logging sensitive payloads.
