// Pins configuration for the two ultrasonic sensors
const int trig1 = 2; // Outer Sensor Trigger Pin
const int echo1 = 3; // Outer Sensor Echo Pin
const int trig2 = 4; // Inner Sensor Trigger Pin
const int echo2 = 5; // Inner Sensor Echo Pin

const int distThreshold = 60; // Threshold distance in cm (adjust based on doorway width)
const unsigned long timeout = 2500; // 2.5 seconds sequence window

bool s1_triggered = false;
bool s2_triggered = false;
unsigned long triggerTime = 0;

void setup() {
  Serial.begin(9600);
  pinMode(trig1, OUTPUT);
  pinMode(echo1, INPUT);
  pinMode(trig2, OUTPUT);
  pinMode(echo2, INPUT);
}

long getDistance(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  long duration = pulseIn(echo, HIGH, 30000); // 30ms timeout
  if (duration == 0) return 999;
  return duration * 0.034 / 2;
}

void loop() {
  long d1 = getDistance(trig1, echo1);
  long d2 = getDistance(trig2, echo2);

  unsigned long currentMillis = millis();

  // Reset sequence window on timeout
  if ((s1_triggered || s2_triggered) && (currentMillis - triggerTime > timeout)) {
    s1_triggered = false;
    s2_triggered = false;
  }

  // Outer Sensor Triggered First (Entering motion starting)
  if (d1 < distThreshold && !s1_triggered && !s2_triggered) {
    s1_triggered = true;
    triggerTime = currentMillis;
    delay(150); // Debounce / transit delay
  } 
  // Inner Sensor Triggered First (Exiting motion starting)
  else if (d2 < distThreshold && !s1_triggered && !s2_triggered) {
    s2_triggered = true;
    triggerTime = currentMillis;
    delay(150);
  }

  // Check Sequence Match
  if (s1_triggered && d2 < distThreshold && (currentMillis - triggerTime < timeout)) {
    Serial.println("ENTRY");
    s1_triggered = false;
    s2_triggered = false;
    delay(2000); // Cooldown to let person pass completely
  }
  else if (s2_triggered && d1 < distThreshold && (currentMillis - triggerTime < timeout)) {
    Serial.println("EXIT");
    s1_triggered = false;
    s2_triggered = false;
    delay(2000); // Cooldown to let person pass completely
  }
  delay(50);
}
