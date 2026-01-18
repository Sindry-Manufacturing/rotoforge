/*
 * ESP32 Robust Tachometer (Burst Median Filter)
 * * Function: Captures 9 consecutive pulses, sorts them, and reports the median.
 * * Latency: ~18ms at 30k RPM.
 */

#include <Arduino.h>
#include <vector>
#include <algorithm> // Required for sorting

// --- Configuration ---
const int TACH_PIN = 27;       
const int VOLT_PIN = 34;       
const int PULSES_PER_REV = 1;  
const float DIVIDER_RATIO = 1; 

// --- Variables ---
volatile unsigned long lastPulseTime = 0;
volatile unsigned long pulseInterval = 0;
volatile bool newData = false;

// Interrupt Service Routine (Fast)
void IRAM_ATTR handleTachPulse() {
  unsigned long currentTime = esp_timer_get_time();
  // Hardware Debounce: Ignore noise faster than 40,000 RPM (1500us)
  if ((currentTime - lastPulseTime) > 1500) { 
    pulseInterval = currentTime - lastPulseTime;
    lastPulseTime = currentTime;
    newData = true;
  }
}

// Helper: Calculate Median
int getMedian(std::vector<int> val) {
  std::sort(val.begin(), val.end());
  return val[val.size() / 2]; // Return the middle element
}

void setup() {
  Serial.begin(115200);
  pinMode(TACH_PIN, INPUT);
  pinMode(VOLT_PIN, INPUT);
  
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); 

  attachInterrupt(digitalPinToInterrupt(TACH_PIN), handleTachPulse, RISING);
  Serial.println("START"); 
}

void loop() {
  // 1. Collect Burst of 9 Samples
  std::vector<int> rpmSamples;
  int samplesNeeded = 9; 

  // Timeout safety: Give up if collection takes too long (e.g. motor stopped)
  unsigned long startBurst = millis();
  
  while(rpmSamples.size() < samplesNeeded && (millis() - startBurst < 200)) {
    
    // Check for "Stopped" motor (No pulse for 0.5s)
    if (esp_timer_get_time() - lastPulseTime > 500000) {
       // Fill remaining samples with 0 to force the median down quickly
       while(rpmSamples.size() < samplesNeeded) rpmSamples.push_back(0);
       break;
    }

    // Capture Pulse
    if (newData) {
      noInterrupts();
      unsigned long interval = pulseInterval;
      newData = false; // Reset flag
      interrupts();

      if (interval > 0) {
        // Calculate RPM instantly
        int r = (int)(1000000.0 / interval * 60.0 / PULSES_PER_REV);
        rpmSamples.push_back(r);
      }
    }
    // NO DELAY HERE: We want to catch the very next pulse immediately.
  }

  // 2. Calculate Median RPM
  int finalRPM = 0;
  if (rpmSamples.size() > 0) {
    finalRPM = getMedian(rpmSamples);
  }

  // 3. Read Voltage (Quick Average)
  long adcSum = 0;
  for(int i=0; i<10; i++) {
    adcSum += analogRead(VOLT_PIN);
    delayMicroseconds(10);
  }
  float voltage = (adcSum / 10.0 / 4095.0) * 3.3 * DIVIDER_RATIO;

  // 4. Output to Serial
  Serial.print(millis());
  Serial.print(",");
  Serial.print(voltage, 2); 
  Serial.print(",");
  Serial.println(finalRPM);
  
  // Optional: Main loop delay to control CSV file size
  // delay(50); 
}