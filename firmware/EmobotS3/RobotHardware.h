#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_NeoPixel.h>
#include <ESP32Servo.h>
#include <RevEng_PAJ7620.h>
#include <Preferences.h>
#include "Clips.h"

namespace emobot {
static const char* const clips[] = {"heart","calendar","face_id","cola","laugh","dumbbell","skateboard","battery","basketball","rugby","alarm","screen","wifi","youtube","tv","movie","cat","write","phone","sunny","cloudy","rainy","windy","snow","beer","walk","shit","cry","puzzled","football","volleyball","badminton","rice","gym","boat","thinking","money","wait","plane","rocket","ok","love"};
static const char* const eyes[] = {"eye_blink","eye_happy","eye_sad","eye_anger","eye_surprise","eye_left","eye_right"};
static const char* const heads[] = {"head_left","head_right","head_up","head_down","head_nod","head_shake","head_roll_left","head_roll_right","head_center"};
inline int lookup(const String& name, const char* const* values, size_t count) {
  for (size_t i=0; i<count; ++i) if (name == values[i]) return i;
  return -1;
}
inline bool validAction(const String& name) {
  return name == "delay" || lookup(name, clips, 42)>=0 || lookup(name, eyes, 7)>=0 || lookup(name, heads, 9)>=0;
}

struct Step { String name; uint16_t duration; };
class Hardware {
  Adafruit_SSD1306 screen{128,64,&Wire,-1};
  Adafruit_NeoPixel led{1,48,NEO_GRB+NEO_KHZ800};
  Servo yaw, pitch;
  RevEng_PAJ7620 gesture;
  Preferences state;
  Step plan[12];
  int length=0, current=0, cx=90, cy=90;
  uint32_t started=0, drawn=0, idleBlink=0;
  bool screenReady=false, sensorReady=false, enabled=true;
  int lastFrame=-1;
  void pose(int x, int y) {
    yaw.write(constrain(x, max(0,cx-25), min(180,cx+25)));
    pitch.write(constrain(y, max(0,cy-45), min(180,cy+45)));
  }
  void face(int expression, float phase) {
    if (!screenReady) return;
    screen.clearDisplay();
    int shift = expression==5 ? -12 : expression==6 ? 12 : 0;
    int height = expression==0 && phase<0.5f ? 4 : expression==4 ? 34 : 26;
    for (int x : {26+shift, 76+shift}) {
      screen.fillRoundRect(x, 32-height/2, 26, height, min(7,height/2), SSD1306_WHITE);
      if (expression==1) screen.fillCircle(x+13, 22, 16, SSD1306_BLACK);
      if (expression==2) screen.fillTriangle(x,17,x+26,17,x+26,30,SSD1306_BLACK);
      if (expression==3) screen.fillTriangle(x,17,x+26,17,x,30,SSD1306_BLACK);
    }
    screen.display();
  }
  void bitmap(int clip, int frame) {
    uint8_t pixels[512];
    uint32_t at=pgm_read_dword(clipOffsets+clip*28+frame);
    uint32_t end=pgm_read_dword(clipOffsets+clip*28+frame+1);
    size_t cursor=0;
    while (at+1<end && cursor<sizeof(pixels)) {
      uint8_t count=pgm_read_byte(clipPixels+at++), value=pgm_read_byte(clipPixels+at++);
      if (cursor+count>sizeof(pixels)) return;
      memset(pixels+cursor,value,count); cursor+=count;
    }
    if (cursor!=sizeof(pixels) || !screenReady) return;
    screen.clearDisplay(); screen.drawBitmap(32,0,pixels,64,64,SSD1306_WHITE); screen.display();
  }
public:
  void begin() {
    Wire.begin(8,9);
    screenReady=screen.begin(SSD1306_SWITCHCAPVCC,0x3c);
    sensorReady=gesture.begin();
    state.begin("emobot",false);
    cx=constrain(state.getInt("cx",90),45,135); cy=constrain(state.getInt("cy",90),45,135);
    yaw.setPeriodHertz(50); pitch.setPeriodHertz(50);
    yaw.attach(12,500,2400); pitch.attach(13,500,2400);
    pose(cx,cy); led.begin(); led.setBrightness(24); face(1,0);
  }
  bool accept(JsonArrayConst actions) {
    if (actions.size()>12 || length) return false;
    uint32_t total=0;
    for (JsonVariantConst item : actions) {
      if (!item.is<JsonObjectConst>() || !item["action"].is<const char*>() || !item["duration"].is<int>()) return false;
      int duration=item["duration"].as<int>();
      if (!validAction(item["action"].as<String>()) || duration<50 || duration>5000) return false;
      total+=duration;
    }
    if (total>20000) return false;
    length=actions.size(); current=0;
    int i=0;
    for (JsonVariantConst item : actions) plan[i++]={item["action"].as<String>(),item["duration"].as<uint16_t>()};
    started=millis(); lastFrame=-1;
    return true;
  }
  String command(const String& command) {
    if (command=="on" || command=="off") { enabled=command=="on"; length=0; pose(cx,cy); return "ok"; }
    if (command=="mac_address") return WiFi.macAddress();
    if (command=="reboot" || command=="restart") { ESP.restart(); return "restarting"; }
    int delta=0; char trailing=0;
    if (sscanf(command.c_str(),"adjust_x %d %c",&delta,&trailing)==1 || sscanf(command.c_str(),"adjust_y %d %c",&delta,&trailing)==1) {
      if (delta < -45 || delta >45) return "invalid calibration";
      if (command.startsWith("adjust_x")) { cx=constrain(cx+delta,45,135); state.putInt("cx",cx); }
      else { cy=constrain(cy+delta,45,135); state.putInt("cy",cy); }
      pose(cx,cy); return "ok";
    }
    int x,y,duration;
    if (sscanf(command.c_str(),"head_move %d %d %d %c",&x,&y,&duration,&trailing)==3 && x>=0 && x<=180 && y>=0 && y<=180 && duration>=50 && duration<=5000) {
      length=0; pose(x,y); return "ok";
    }
    return "unknown command";
  }
  void tick(uint8_t voicePhase) {
    uint32_t time=millis();
    led.setPixelColor(0,voicePhase==1 ? led.Color(50,30,0) : voicePhase==2 ? led.Color(0,0,50) : voicePhase==3 ? led.Color(0,50,0) : 0); led.show();
    if (!enabled) return;
    if (!length) {
      if (time-idleBlink>4000) { face(0,0); idleBlink=time; }
      else if (time-idleBlink>150 && time-idleBlink<220) face(1,0);
      return;
    }
    Step& step=plan[current];
    uint32_t elapsed=time-started;
    if (elapsed>=step.duration) {
      if (++current>=length) { length=0; pose(cx,cy); face(1,0); }
      started=time; lastFrame=-1; return;
    }
    float phase=float(elapsed)/step.duration;
    int head=lookup(step.name,heads,9), eye=lookup(step.name,eyes,7), clip=lookup(step.name,clips,42);
    if (head>=0) {
      float wave=sinf(phase*4*PI);
      int x=cx, y=cy;
      if (head==0) x-=20; if (head==1) x+=20; if (head==2) y-=25; if (head==3) y+=25;
      if (head==4) y+=int(20*wave); if (head==5) x+=int(20*wave);
      if (head==6 || head==7) { x+=int(20*cosf(phase*2*PI)); y+=int(20*sinf(phase*2*PI)*(head==6?1:-1)); }
      pose(x,y);
    }
    if (time-drawn<30) return;
    drawn=time;
    if (eye>=0) face(eye,phase);
    if (clip>=0) {
      int frame=min(27,int(phase*28));
      if (frame!=lastFrame) { bitmap(clip,frame); lastFrame=frame; }
    }
  }
  Gesture readGesture() { return sensorReady && enabled ? gesture.readGesture() : GES_NONE; }
};
}
