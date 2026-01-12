import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def run_test():
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Load the test HTML file
        file_path = os.path.abspath("tests/js/test_agenda_speaker_list.html")
        driver.get(f"file://{file_path}")

        # Wait for potential async operations (simple wait for now)
        time.sleep(2)

        # Get the results from the page
        results_container = driver.find_element(By.ID, "test-results")
        results_text = results_container.text

        print("Test Output:")
        print(results_text)

        # Check for failures
        if "FAIL" in results_text:
            print("\n❌ Tests Failed!")
            exit(1)
        elif "PASS" in results_text:
            print("\n✅ All Tests Passed!")
            exit(0)
        else:
            print("\n⚠️ unknown test state.")
            exit(1)

    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)
    finally:
        driver.quit()

if __name__ == "__main__":
    run_test()
