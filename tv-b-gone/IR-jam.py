import time
import pigpio
# This python script just sends blank 38kHz signal, just like the old-school NE555 IR jammer
# === Configuration ===
GPIO_IR_LED = 17
# =====================
pi = pigpio.pi()
pi.set_mode(GPIO_IR_LED, pigpio.OUTPUT)
pi.set_PWM_range(GPIO_IR_LED, 255)
pi.set_PWM_dutycycle(GPIO_IR_LED, 128)
pi.set_PWM_frequency(GPIO_IR_LED, 38000)
if __name__ == "__main__":
     try:
        while True:
           time.sleep(1)
     except KeyboardInterrupt:
        print("\nInterrupted by user.")
     finally:
         pi.set_PWM_dutycycle(GPIO_IR_LED, 0)
         pi.stop()
