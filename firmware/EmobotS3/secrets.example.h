#pragma once
// Copy to secrets.h (ignored by Git). Obtain service keys and trusted PEM root CAs yourself.
#define EMOBOT_API_KEY ""
#define EMOBOT_CHAT_URL "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
#define EMOBOT_CHAT_MODEL "qwen3.6-plus"
#define EMOBOT_ASR_URL "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
#define EMOBOT_ASR_MODEL "qwen3-asr-flash"
#define EMOBOT_TTS_APP ""
#define EMOBOT_TTS_TOKEN ""
#define EMOBOT_TTS_CLUSTER "volcano_tts"
#define EMOBOT_TTS_VOICE "BV213_streaming"
#define EMOBOT_AP_PASSWORD "emobot2026"
// Concatenate the current trusted roots for Alibaba and ByteDance as PEM strings.
// Empty means independent cloud voice stays disabled. TLS verification is never bypassed.
#define EMOBOT_ROOT_CA ""
