import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_pcm_parser_bounds_under_fuzz(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("C++ host compiler unavailable; firmware cross-build still runs in CI")
    source = tmp_path / "parser.cpp"
    source.write_text(r"""
#include "WireGuard.h"
#include <cassert>
#include <random>
#include <vector>
int main() {
  emobot::AudioPacket packet;
  uint8_t valid[] = {0x11,0xb3,0,0,0xff,0xff,0xff,0xff,0,0,0,4,1,0,2,0};
  assert(emobot::parseAudio(valid,sizeof(valid),packet));
  assert(packet.last && packet.bytes==4 && packet.pcm==valid+12);
  for (size_t n=0;n<sizeof(valid);++n) assert(!emobot::parseAudio(valid,n,packet));
  valid[2]=0x10; assert(!emobot::parseAudio(valid,sizeof(valid),packet)); valid[2]=0;
  valid[11]=5; assert(!emobot::parseAudio(valid,sizeof(valid),packet));
  std::mt19937 random(20261001);
  for (int iteration=0;iteration<50000;++iteration) {
    std::vector<uint8_t> bytes(random()%128);
    for (auto& byte:bytes) byte=random()%256;
    if (emobot::parseAudio(bytes.data(),bytes.size(),packet) && packet.bytes) {
      assert(packet.pcm>=bytes.data() && packet.pcm+packet.bytes<=bytes.data()+bytes.size());
      assert(packet.bytes%2==0);
    }
  }
}
""")
    binary = tmp_path / "parser"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-fsanitize=address,undefined",
            "-I",
            str(ROOT / "firmware/EmobotS3"),
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(binary)], check=True, capture_output=True, timeout=20)
