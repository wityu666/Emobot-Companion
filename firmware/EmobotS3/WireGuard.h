#pragma once
#include <cstddef>
#include <cstdint>

namespace emobot {
struct AudioPacket {
  const uint8_t *pcm = nullptr;
  size_t bytes = 0;
  bool last = false;
};
inline uint32_t readBE(const uint8_t *bytes) {
  return (uint32_t(bytes[0]) << 24) | (uint32_t(bytes[1]) << 16) | (uint32_t(bytes[2]) << 8) |
         bytes[3];
}
inline bool parseAudio(const uint8_t *bytes, size_t length, AudioPacket &packet) {
  packet = {};
  if (!bytes || length < 4 || bytes[0] >> 4 != 1 || bytes[2] != 0)
    return false;
  size_t header = (bytes[0] & 15) * 4;
  if (header < 4 || header > length || (bytes[1] >> 4) != 11)
    return false;
  uint8_t flags = bytes[1] & 15;
  if (!flags)
    return header == length;
  if (flags > 3 || length - header < 8)
    return false;
  int32_t sequence = static_cast<int32_t>(readBE(bytes + header));
  if ((flags == 1 && sequence <= 0) || (flags >= 2 && sequence >= 0))
    return false;
  size_t size = readBE(bytes + header + 4);
  if (size % 2 || size > length - header - 8)
    return false;
  packet.pcm = bytes + header + 8;
  packet.bytes = size;
  packet.last = sequence < 0;
  return true;
}
} // namespace emobot
