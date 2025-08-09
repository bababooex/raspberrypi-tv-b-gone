import sys
import time
import pigpio
# Better version with  variable frequency and predefined gpio pin in bash script
def main():
    if len(sys.argv) != 3:
        print("Usage: IR-jam.py <frequency> <gpio_pin>")
        sys.exit(1)

    gpio_pin = int(sys.argv[2])
    frequency = int(sys.argv[1])

    pi = pigpio.pi()

    pi.set_mode(gpio_pin, pigpio.OUTPUT)
    pi.set_PWM_range(gpio_pin, 255)
    pi.set_PWM_dutycycle(gpio_pin, 128)  # 50% DCL
    pi.set_PWM_frequency(gpio_pin, frequency)

    try:
        print(f"Sending {frequency} square wave PWM. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        pi.set_PWM_dutycycle(gpio_pin, 0)
        pi.stop()

if __name__ == "__main__":
    main()
