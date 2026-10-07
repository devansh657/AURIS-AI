# Third-Party Notices

## Three.js

AURIS vendors `three` 0.185.1 for the local WebGL neural command-centre visualization. Three.js is distributed under the MIT License; the complete license is preserved at `web/vendor/LICENSE`.

- Package: https://www.npmjs.com/package/three/v/0.185.1
- Vendored module SHA-256: `86BCEE248B64F44BCFC23C331AE74619061957D59CAB040171DCB6FB5900BEB6`

## Kokoro ONNX

AURIS uses `kokoro-onnx` 0.6.1 and the Kokoro v1.0 fp16 model for its primary local neural speech synthesis. The wrapper is distributed under the MIT License and its project identifies the Kokoro model license as Apache 2.0.

- Project: https://github.com/thewh1teagle/kokoro-onnx
- Model release: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

The product-facing name `AURIS Vale` identifies AURIS's selected speaker and delivery configuration; it does not imply ownership of the underlying model or training data.

## Piper

AURIS uses `piper-tts` 1.6.0 for local neural speech synthesis. Piper is maintained by the Open Home Foundation and distributed under the MIT License.

- Project: https://github.com/OHF-Voice/piper1-gpl
- Package: https://pypi.org/project/piper-tts/

## Northern English Male Voice Model

The local `en_GB-northern_english_male-medium` Piper model is distributed by the Piper voices project. Its model card identifies the dataset license as Creative Commons Attribution-ShareAlike 4.0.

- Model: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/northern_english_male/medium
- License: https://creativecommons.org/licenses/by-sa/4.0/

Piper and its Northern English voice remain startup-only local fallbacks when the primary Kokoro CUDA runtime is unavailable.
