import json
import time
import random
import os
import re
from datetime import datetime
import requests
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from anticaptchaofficial.imagecaptcha import imagecaptcha
import telegram
from telegram.ext import Updater, MessageHandler, Filters
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    ElementClickInterceptedException,
)

# --- Configuration Loading ---
try:
    with open("config.json", "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    print("ERROR: config.json not found. Please create it.")
    exit()
except json.JSONDecodeError:
    print("ERROR: config.json is not valid JSON.")
    exit()
# --- End Configuration Loading ---

# --- Directory Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Subdirectories for screenshots
LOGIN_SCREENSHOT_DIR = os.path.join(SCREENSHOT_DIR, "login")
CAPTCHA_SCREENSHOT_DIR = os.path.join(SCREENSHOT_DIR, "captcha")
SEARCH_SCREENSHOT_DIR = os.path.join(SCREENSHOT_DIR, "search_results")
ITEM_SCREENSHOT_DIR = os.path.join(SCREENSHOT_DIR, "items")
ERROR_SCREENSHOT_DIR = os.path.join(SCREENSHOT_DIR, "errors")
BLOCK_SCREENSHOT_DIR = os.path.join(SCREENSHOT_DIR, "block_pages") # New

# Subdirectories for logs
PAGE_LOG_DIR = os.path.join(LOG_DIR, "pages")
ERROR_LOG_DIR = os.path.join(LOG_DIR, "errors")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGIN_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(CAPTCHA_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(SEARCH_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(ITEM_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(ERROR_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(BLOCK_SCREENSHOT_DIR, exist_ok=True) # New
os.makedirs(PAGE_LOG_DIR, exist_ok=True)
os.makedirs(ERROR_LOG_DIR, exist_ok=True)

# --- File Paths ---
COOKIE_FILE = os.path.join(DATA_DIR, "xianyu_cookies.json")
KNOWN_PRODUCTS_FILE = os.path.join(DATA_DIR, "known_products.json")
# --- End Directory Setup & File Paths ---

# --- Helper Function for Conditional Logging ---
def log_message(message, level="info", photo_path=None, caption=""):
    """Sends message/photo to Telegram only if debug messages are enabled."""
    if CONFIG.get("SEND_DEBUG_MESSAGES", True):
        try:
            if photo_path and os.path.exists(photo_path):
                 with open(photo_path, "rb") as photo_file:
                      telegram_bot.send_photo(
                          chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                          photo=photo_file,
                          caption=caption or message # Use message as caption if none provided
                      )
            elif message:
                telegram_bot.send_message(
                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                    text=message
                )
        except Exception as e:
            print(f"Error sending debug message/photo to Telegram: {e}")
    # Always print to console for local debugging
    print(f"[{level.upper()}] {message or caption}")

# --- Initialize Telegram Bot ---
try:
    telegram_bot = telegram.Bot(token=CONFIG["TELEGRAM_TOKEN"])
except Exception as e:
    print(f"Error initializing Telegram bot: {e}")
    # Create a dummy bot that logs instead of sending messages
    class DummyBot:
        def send_message(self, chat_id, text, **kwargs):
             log_message(text)

        def send_photo(self, chat_id, photo, **kwargs):
             caption = kwargs.get('caption', '')
             log_message(caption, photo_path="dummy_path")

    telegram_bot = DummyBot()
# --- End Bot Initialization ---

# Message IDs to track ongoing captcha conversations
ACTIVE_CAPTCHA_MSG_ID = None

def get_yuan_to_euro_rate():
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/CNY", timeout=10)
        data = response.json()
        return data["rates"]["EUR"]
    except Exception as e:
        print(f"Error getting exchange rate: {e}")
        return 0.128  # Fallback approximate rate

def yuan_to_euro(yuan_str):
    try:
        yuan_str = yuan_str.replace("¥", "").replace(",", "").strip()
        if "-" in yuan_str:
            parts = yuan_str.split("-")
            yuan_values = [float(part.strip()) for part in parts]
            rate = get_yuan_to_euro_rate()
            euro_values = [value * rate for value in yuan_values]
            return f"€{euro_values[0]:.2f} - €{euro_values[1]:.2f}"
        else:
            numeric_match = re.search(r'(\d+\.?\d*)', yuan_str)
            if numeric_match:
                yuan = float(numeric_match.group(1))
                rate = get_yuan_to_euro_rate()
                euro = yuan * rate
                return f"€{euro:.2f}"
            return "Price format unknown"
    except Exception as e:
        print(f"Error converting currency: {e}")
        return "€N/A"

# *** UPDATED setup_browser with more anti-detection options ***
def setup_browser():
    try:
        options = uc.ChromeOptions()
        options.add_argument(f"user-agent={CONFIG['USER_AGENT']}")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Common stability options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")

        # Anti-detection specific options
        options.add_argument("--disable-infobars") # Disable "Chrome is being controlled..."
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=zh-CN,zh;q=0.9") # Set language
        options.add_argument("--disable-features=UserAgentClientHint") # Disable client hints

        # Headless specific settings
        if CONFIG["HEADLESS"]:
            options.add_argument("--headless=new") # Use the new headless mode
            options.add_argument("--disable-features=IsolateOrigins,site-per-process") # May help in some headless scenarios

        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        print(f"Error creating undetected-chromedriver: {e}")
        # Fallback logic remains the same...
        try:
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            options = webdriver.ChromeOptions()
            options.add_argument(f"user-agent={CONFIG['USER_AGENT']}")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            if CONFIG["HEADLESS"]:
                options.add_argument("--headless=new")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(60)
            return driver
        except Exception as e2:
            print(f"Error creating standard chromedriver: {e2}")
            raise Exception(f"Failed to initialize any browser: {e}, {e2}")
# *** END UPDATED setup_browser ***

def load_cookies(driver):
    try:
        driver.get("https://www.goofish.com/")
        time.sleep(3)

        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
                for cookie in cookies:
                    if 'expiry' in cookie:
                        del cookie['expiry']
                    try:
                        driver.add_cookie(cookie)
                    except Exception as cookie_error:
                        print(f"Error adding cookie: {cookie_error}")
            driver.refresh()
            time.sleep(3)
            return True
    except Exception as e:
        log_message(f"Error loading cookies: {str(e)}", level="error")
    return False

def save_cookies(driver):
    try:
        cookies = driver.get_cookies()
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
    except Exception as e:
        log_message(f"Error saving cookies: {str(e)}", level="error")

def login_required(driver):
    """Checks for specific, visible login modal/overlay elements."""
    try:
        login_modal_selectors = [
            "div[class*='login-dialog'][style*='display: block']",
            "div.login-popup[style*='display: block']",
            "div.login-overlay[style*='display: block']",
            "div[data-spm='login'][style*='display: block']",
            "iframe[src*='login.taobao.com']",
            "iframe[src*='login.xianyu.alibaba.com']"
        ]

        for selector in login_modal_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        print(f"Login required detected by visible element: {selector}")
                        return True
            except NoSuchElementException:
                continue
            except Exception as e:
                print(f"Minor error checking login selector '{selector}': {e}")
                continue

        print("No visible login modal detected.")
        return False

    except Exception as e:
        print(f"Error checking login status: {e}. Assuming login is not required.")
        return False

def handle_login(driver):
    telegram_bot.send_message(
        chat_id=CONFIG["TELEGRAM_CHAT_ID"],
        text="Login required. Attempting to capture QR code on current page..."
    )

    try:
        qr_code_xpath = "//div[contains(@class, 'qrcode')] | //canvas[contains(@class, 'qrcode')] | //img[contains(@class, 'qrcode')]"
        qr_screenshot_path = os.path.join(LOGIN_SCREENSHOT_DIR, "qr_code.png")
        fallback_screenshot_path = os.path.join(LOGIN_SCREENSHOT_DIR, "login_page_fallback.png")
        error_screenshot_path = os.path.join(LOGIN_SCREENSHOT_DIR, "login_page_error.png")
        notfound_screenshot_path = os.path.join(LOGIN_SCREENSHOT_DIR, "login_qr_not_found.png")

        try:
            WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.XPATH, qr_code_xpath))
            )
        except TimeoutException:
            telegram_bot.send_message(
                chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                text="Could not find QR code element on the page after waiting."
            )
            driver.save_screenshot(notfound_screenshot_path)
            with open(notfound_screenshot_path, "rb") as photo:
                telegram_bot.send_photo(
                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                    photo=photo,
                    caption="Page state when QR code was expected but not found"
                )
            return False

        try:
            qr_elements = driver.find_elements(By.XPATH, qr_code_xpath)
            qr_element_to_screenshot = None
            for elem in qr_elements:
                if elem.is_displayed():
                    qr_element_to_screenshot = elem
                    break

            if qr_element_to_screenshot:
                qr_element_to_screenshot.screenshot(qr_screenshot_path)
                with open(qr_screenshot_path, "rb") as qr_photo:
                    telegram_bot.send_photo(
                        chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                        photo=qr_photo,
                        caption="QR Code - scan with Xianyu app"
                    )
            else:
                driver.save_screenshot(fallback_screenshot_path)
                with open(fallback_screenshot_path, "rb") as photo:
                    telegram_bot.send_photo(
                        chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                        photo=photo,
                        caption="Login required - please scan QR code (fallback screenshot)"
                    )
        except Exception as qr_error:
            driver.save_screenshot(error_screenshot_path)
            with open(error_screenshot_path, "rb") as photo:
                telegram_bot.send_photo(
                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                    photo=photo,
                    caption=f"Login required - please scan QR code (error screenshot: {str(qr_error)})"
                )

        max_wait = 300
        start_time = time.time()

        while time.time() - start_time < max_wait:
            if not login_required(driver):
                telegram_bot.send_message(
                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                    text="Login successful!"
                )
                time.sleep(3)
                save_cookies(driver)
                return True
            time.sleep(5)

        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text="Login timeout. Please try again."
        )
        return False

    except Exception as e:
        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text=f"Login handling error: {str(e)}"
        )
        try:
            error_handling_screenshot = os.path.join(ERROR_SCREENSHOT_DIR, "login_handling_error.png")
            driver.save_screenshot(error_handling_screenshot)
            with open(error_handling_screenshot, "rb") as photo:
                telegram_bot.send_photo(
                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                    photo=photo,
                    caption="Login handling error state"
                )
        except:
            pass
        return False

def detect_slider_captcha(driver):
    try:
        captcha_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'captcha') or contains(@class, 'slider') or contains(@class, 'verify')]")
        for elem in captcha_elements:
            if elem.is_displayed():
                print("Visible captcha element detected.")
                return True

        captcha_indicators = [
            "slide", "slider", "滑块", "拖动", "验证", "captcha",
            "sigue el camino", "deslizante", "安全验证", "security verification",
            "拖动滑块", "完成拼图"
        ]
        page_source = driver.page_source.lower()
        if any(indicator.lower() in page_source for indicator in captcha_indicators):
             print("Captcha indicator found in page source.")
             return True

        return False
    except Exception as e:
        print(f"Error detecting captcha: {e}")
        return False

def solve_slider_captcha_with_anticaptcha(driver):
    try:
        captcha_full_path = os.path.join(CAPTCHA_SCREENSHOT_DIR, "captcha_full.png")
        captcha_area_path = os.path.join(CAPTCHA_SCREENSHOT_DIR, "captcha_area.png")
        driver.save_screenshot(captcha_full_path)
        slider_elements = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'captcha')] | //div[contains(@class, 'slider')] | //div[contains(@class, 'verify')]"
        )

        slider_element = None
        for elem in slider_elements:
            if elem.is_displayed():
                slider_element = elem
                break

        if not slider_element:
            print("Could not find visible slider element for Anti-Captcha.")
            return False

        slider_element.screenshot(captcha_area_path)

        solver = imagecaptcha()
        solver.set_verbose(1)
        solver.set_key(CONFIG["ANTICAPTCHA_KEY"])
        result = solver.solve_and_return_solution(captcha_area_path)

        if not result or "error" in str(result).lower():
            print(f"Anti-Captcha failed or returned error: {result}")
            return False

        try:
            slider_handles = driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'slider')]//span | //div[contains(@class, 'handler')] | //span[contains(@class, 'btn_slide')]"
            )

            slider_handle = None
            for handle in slider_handles:
                if handle.is_displayed():
                    slider_handle = handle
                    break

            if not slider_handle:
                print("Could not find visible slider handle.")
                return False

            slider_container = slider_element
            container_width = slider_container.size['width']
            offset = container_width * 0.7

            actions = ActionChains(driver)
            actions.click_and_hold(slider_handle)

            current_offset = 0
            step = 5
            while current_offset < offset:
                move_by = min(step, offset - current_offset)
                actions.move_by_offset(move_by, random.uniform(-2, 2))
                actions.pause(random.uniform(0.01, 0.05))
                current_offset += move_by

            actions.release()
            actions.perform()
            time.sleep(4)

            if not detect_slider_captcha(driver):
                log_message("Captcha solved automatically!")
                return True
            else:
                print("Captcha still detected after automatic attempt.")
                return False

        except Exception as e:
            log_message(f"Error performing slider action: {str(e)}", level="error")
            return False

    except Exception as e:
        log_message(f"Automated captcha solving error: {str(e)}", level="error")

    return False

def handle_remote_captcha_solving(driver):
    global ACTIVE_CAPTCHA_MSG_ID

    try:
        captcha_remote_path = os.path.join(CAPTCHA_SCREENSHOT_DIR, "captcha_remote.png")
        captcha_failed_path = os.path.join(CAPTCHA_SCREENSHOT_DIR, "captcha_failed.png")
        driver.save_screenshot(captcha_remote_path)
        with open(captcha_remote_path, "rb") as photo:
            msg = telegram_bot.send_photo(
                chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                photo=photo,
                caption="🔴 *CAPTCHA DETECTED!*\n\nPlease solve this slider captcha by telling me how far to slide (e.g., '60%' means slide 60% of the way).\n\nOr type 'remote access' if you need instructions for remote access."
            )
            ACTIVE_CAPTCHA_MSG_ID = msg.message_id

        updater = Updater(token=CONFIG["TELEGRAM_TOKEN"])
        dispatcher = updater.dispatcher

        def captcha_response_handler(update, context):
            global ACTIVE_CAPTCHA_MSG_ID

            if update.message.reply_to_message and update.message.reply_to_message.message_id == ACTIVE_CAPTCHA_MSG_ID:
                try:
                    response = update.message.text.strip().lower()

                    if "remote access" in response:
                        telegram_bot.send_message(
                            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                            text="To set up remote access:\n\n1. Install Chrome Remote Desktop on the server\n2. Create a session and share the access code\n3. Use Chrome Remote Desktop app to connect\n\nLet me know when you're connected by replying 'connected'"
                        )
                        return

                    if "connected" in response:
                        telegram_bot.send_message(
                            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                            text="Great! Please solve the captcha in the browser window, then reply 'done' when solved"
                        )
                        return

                    if "done" in response:
                        if not detect_slider_captcha(driver):
                            telegram_bot.send_message(
                                chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                                text="Captcha solved successfully! Continuing..."
                            )
                            ACTIVE_CAPTCHA_MSG_ID = None
                            updater.stop()
                            return True
                        else:
                            telegram_bot.send_message(
                                chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                                text="Captcha still appears to be present. Please try again."
                            )
                            return

                    if "%" in response:
                        percentage = int(response.replace("%", ""))
                        if 0 <= percentage <= 100:
                            slider_handles = driver.find_elements(
                                By.XPATH,
                                "//div[contains(@class, 'slider')]//span | //div[contains(@class, 'handler')] | //span[contains(@class, 'btn_slide')]"
                            )

                            slider_handle = None
                            for handle in slider_handles:
                                if handle.is_displayed():
                                    slider_handle = handle
                                    break

                            if not slider_handle:
                                telegram_bot.send_message(
                                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                                    text="Couldn't find the visible slider element. Please try remote access."
                                )
                                return

                            slider_container = driver.find_element(
                                By.XPATH,
                                "//div[contains(@class, 'captcha')] | //div[contains(@class, 'slider-container')] | //div[contains(@class, 'verify')]"
                            )
                            container_width = slider_container.size['width']
                            offset = (container_width * percentage) / 100

                            actions = ActionChains(driver)
                            actions.click_and_hold(slider_handle)

                            current_offset = 0
                            step = 5
                            while current_offset < offset:
                                move_amount = min(step, offset - current_offset)
                                actions.move_by_offset(move_amount, random.uniform(-2, 2))
                                actions.pause(random.uniform(0.01, 0.05))
                                current_offset += move_amount

                            actions.release()
                            actions.perform()
                            time.sleep(3)

                            if not detect_slider_captcha(driver):
                                telegram_bot.send_message(
                                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                                    text=f"Captcha solved successfully with {percentage}% slide! Continuing..."
                                )
                                ACTIVE_CAPTCHA_MSG_ID = None
                                updater.stop()
                                return True
                            else:
                                driver.save_screenshot(captcha_failed_path)
                                with open(captcha_failed_path, "rb") as photo:
                                    telegram_bot.send_photo(
                                        chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                                        photo=photo,
                                        caption=f"Sliding to {percentage}% didn't solve the captcha. Please try a different value or use remote access."
                                    )
                        else:
                            telegram_bot.send_message(
                                chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                                text="Please provide a percentage between 0 and 100"
                            )
                except Exception as e:
                    telegram_bot.send_message(
                        chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                        text=f"Error processing your response: {str(e)}"
                    )

        captcha_handler = MessageHandler(Filters.text & ~Filters.command, captcha_response_handler)
        dispatcher.add_handler(captcha_handler)
        updater.start_polling()

        timeout = 300
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not ACTIVE_CAPTCHA_MSG_ID:
                return True
            time.sleep(1)

            if not detect_slider_captcha(driver):
                telegram_bot.send_message(
                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                    text="Captcha appears to be solved! Continuing..."
                )
                updater.stop()
                return True

        updater.stop()
        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text="Captcha solving timeout. Will retry on next cycle."
        )
        return False

    except Exception as e:
        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text=f"Remote captcha handling error: {str(e)}"
        )
        return False

def handle_captcha(driver):
    if detect_slider_captcha(driver):
        log_message("Captcha detected! Attempting automatic solution...")

        for attempt in range(3):
            if solve_slider_captcha_with_anticaptcha(driver):
                return True
            print(f"Automatic captcha attempt {attempt + 1} failed.")
            time.sleep(2)

        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text="Automatic captcha solving failed. Requesting manual help..."
        )
        return handle_remote_captcha_solving(driver)

    return True  # No captcha detected

def extract_products(driver, query):
    products = {}

    try:
        screenshot_filename = os.path.join(SEARCH_SCREENSHOT_DIR, f"search_{query.replace(' ', '_')}.png")
        driver.save_screenshot(screenshot_filename)
        log_message(f"Search results for '{query}' (Sorted by Newest)", photo_path=screenshot_filename)

        item_selector = "a[class*='feeds-item-wrap']"

        try:
            print(f"Waiting for item cards using selector: '{item_selector}'")
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, item_selector))
            )
            print("Potential item card(s) found.")
        except TimeoutException:
             log_message(f"Error: Could not detect any item cards using selector '{item_selector}' after sorting and waiting. Page structure might have changed.", level="error")
             page_source_path = os.path.join(PAGE_LOG_DIR, f"page_source_no_items_{query.replace(' ', '_')}.html")
             page_source = driver.page_source
             with open(page_source_path, "w", encoding="utf-8") as f:
                 f.write(page_source)
             return {}

        try:
            items = driver.find_elements(By.CSS_SELECTOR, item_selector)
            if not items:
                 raise Exception("Selector found during wait, but find_elements returned empty list.")
            log_message(f"Found {len(items)} items using selector '{item_selector}'")
        except Exception as e:
            log_message(f"Error finding items with selector '{item_selector}': {e}. Saving page source.", level="error")
            page_source_path = os.path.join(PAGE_LOG_DIR, f"page_source_find_items_error_{query.replace(' ', '_')}.html")
            page_source = driver.page_source
            with open(page_source_path, "w", encoding="utf-8") as f:
                f.write(page_source)
            return {}

        log_message(f"Processing {len(items)} items for query '{query}'...")

        processed_count = 0
        for item in items:
            try:
                item_href = item.get_attribute('href')
                product_id_match = re.search(r'id=(\d+)', item_href) if item_href else None
                product_id = product_id_match.group(1) if product_id_match else str(hash(item.get_attribute('outerHTML')))

                title = None
                try:
                    title_element = item.find_element(By.CSS_SELECTOR, "div[class*='feeds-content'] span[class*='main-title']")
                    title = title_element.text.strip()
                except NoSuchElementException:
                    print(f"Primary title selector failed for item {product_id}. Trying fallbacks.")
                if not title:
                    title_selectors = [
                        ".item-title", ".item-name", ".title", "h3", ".info-title",
                        "a > span", "div[title]", ".name", ".desc"
                    ]
                    for selector in title_selectors:
                        try:
                            title_elem = item.find_element(By.CSS_SELECTOR, selector)
                            title_text = title_elem.text.strip()
                            if title_text:
                                title = title_text
                                break
                            title_attr = title_elem.get_attribute("title").strip()
                            if title_attr:
                               title = title_attr
                               break
                        except:
                            continue
                if not title:
                    full_text = item.text.strip()
                    if full_text:
                        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                        if lines:
                            potential_titles = [line for line in lines if len(line) > 5 and '¥' not in line and '￥' not in line]
                            title = potential_titles[0] if potential_titles else lines[0]

                if not title or len(title) < 3:
                    print(f"Skipping item - no plausible title found. ID: {product_id}")
                    continue

                price = "Price not found"
                try:
                    price_element = item.find_element(By.CSS_SELECTOR, "div[class*='price-wrap']")
                    price = price_element.text.strip()
                except NoSuchElementException:
                     print(f"Primary price selector failed for item {product_id}. Trying fallbacks.")
                     price_selectors = [
                        ".price", ".item-price", ".price-info", ".money",
                        "span[class*='price']", "div[class*='price']",
                        ".product-price", ".price-container"
                     ]
                     for selector in price_selectors:
                        try:
                            price_elem = item.find_element(By.CSS_SELECTOR, selector)
                            price_text = price_elem.text.strip()
                            if "¥" in price_text or "￥" in price_text:
                                price = price_text
                                break
                        except:
                            continue
                     if price == "Price not found":
                        item_text = item.text
                        price_match = re.search(r'(¥|￥)\s*(\d[\d,\.]*\d)', item_text)
                        if price_match:
                            price = price_match.group(0)

                link = item_href

                item_image = ""
                try:
                    img_element = item.find_element(By.CSS_SELECTOR, "img[class*='feeds-image']")
                    item_image = img_element.get_attribute("src") or img_element.get_attribute("data-src")
                except NoSuchElementException:
                    print(f"Primary image selector failed for item {product_id}. Trying fallback.")
                    try:
                        img_elements = item.find_elements(By.CSS_SELECTOR, "img")
                        if img_elements:
                             item_image = img_elements[0].get_attribute("src") or img_elements[0].get_attribute("data-src")
                    except:
                        pass

                screenshot_path = os.path.join(ITEM_SCREENSHOT_DIR, f"item_{product_id}.png")
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                    time.sleep(0.5)
                    item.screenshot(screenshot_path)
                except Exception as screenshot_error:
                    print(f"Error taking item screenshot: {screenshot_error}")
                    screenshot_path = None

                euro_price = yuan_to_euro(price)

                products[product_id] = {
                    "title": title,
                    "price": price,
                    "price_euro": euro_price,
                    "link": link,
                    "image": item_image,
                    "found_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "screenshot_path": screenshot_path
                }
                processed_count += 1
            except Exception as e:
                print(f"Error processing item {product_id}: {str(e)}")
                try:
                    error_item_path = os.path.join(ERROR_SCREENSHOT_DIR, f"error_item_{product_id}.png")
                    item.screenshot(error_item_path)
                except: pass
                continue

        log_message(f"Successfully processed {processed_count} items for query '{query}'.")

    except Exception as e:
        log_message(f"Critical error during product extraction: {str(e)}", level="error")

    return products


# *** UPDATED apply_sort_by_newest function (v10 - Skip Hover Headless) ***
def apply_sort_by_newest(driver):
    """Attempts to click the sort buttons using hover (headed) and JavaScript click."""
    wait_time = 30

    try:
        # --- Scroll down and up first ---
        print("Scrolling down and up to potentially dismiss overlays...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1.5)
        # --- End Scroll ---

        # --- Try to find and click 'Newly Published' (新发布) ---
        print("Attempting to find 'Newly Published' button (v10)...")
        newly_published_xpath = "//div[contains(@class, 'search-select-container')][.//span[normalize-space()='新发布']]"

        print(f"Waiting up to {wait_time}s for 'Newly Published' visibility...")
        newly_published_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located((By.XPATH, newly_published_xpath))
        )
        print("Found 'Newly Published' button. Scrolling and pausing...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", newly_published_button)
        time.sleep(1)

        # Simulate Hover ONLY if not headless
        if not CONFIG["HEADLESS"]:
            print("Hovering (headed mode)...")
            actions = ActionChains(driver)
            actions.move_to_element(newly_published_button).perform()
            time.sleep(0.5)

        if not newly_published_button.is_displayed():
            raise Exception("'Newly Published' button became hidden.")

        print("Attempting JS click on 'Newly Published'...")
        driver.execute_script("arguments[0].click();", newly_published_button)

        print("Clicked 'Newly Published' (新发布) via JS. Waiting for dropdown...")
        time.sleep(3.5)

        # --- Try to find and click 'Latest' (最新) ---
        print("Attempting to find 'Latest' option (v10)...")
        latest_xpath = "//div[contains(@class, 'search-select-item')][normalize-space()='最新']"

        print(f"Waiting up to {wait_time}s for 'Latest' option visibility...")
        latest_option = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located((By.XPATH, latest_xpath))
        )
        print("Found 'Latest' option. Scrolling and pausing...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", latest_option)
        time.sleep(1)

        # Simulate Hover ONLY if not headless
        if not CONFIG["HEADLESS"]:
            print("Hovering (headed mode)...")
            actions = ActionChains(driver)
            actions.move_to_element(latest_option).perform()
            time.sleep(0.5)

        if not latest_option.is_displayed():
             raise Exception("'Latest' option became hidden.")

        print("Attempting JS click on 'Latest'...")
        driver.execute_script("arguments[0].click();", latest_option)

        print("Clicked 'Latest' (最新) via JS. Waiting for results to reload...")
        time.sleep(5)
        log_message("Applied sort by 'Latest' (via JS).")
        return True # Indicate sorting was successful

    # Keep the same detailed error handling as before
    except TimeoutException as e:
        error_screenshot_path = os.path.join(ERROR_SCREENSHOT_DIR, "sort_timeout_error.png")
        error_html_path = os.path.join(ERROR_LOG_DIR, "sort_timeout_error_source.html")
        err_msg = f"Timeout finding sort buttons (after {wait_time}s). Element likely not visible. Error: {e}"
        print(err_msg)
        try:
            with open(error_html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Saved page source to {error_html_path}")
            driver.save_screenshot(error_screenshot_path)
            log_message(err_msg, level="error", photo_path=error_screenshot_path)
        except Exception as ss_error:
             print(f"Could not save screenshot/source on sort timeout: {ss_error}")

        log_message(f"Warning: Could not find or click sort buttons (Timeout). Proceeding without sorting. Check screenshot/source. Error: {e}", level="warning")
        return False # Indicate sorting failed

    except Exception as e:
        error_screenshot_path = os.path.join(ERROR_SCREENSHOT_DIR, "sort_general_error.png")
        error_html_path = os.path.join(ERROR_LOG_DIR, "sort_general_error_source.html")
        err_msg = f"General error applying sort (v10): {e}"
        print(err_msg)
        log_message(f"Warning: {err_msg}. Proceeding without sorting.", level="warning")
        try:
            with open(error_html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Saved page source to {error_html_path}")
            driver.save_screenshot(error_screenshot_path)
            log_message(err_msg, level="error", photo_path=error_screenshot_path)
        except Exception as ss_error:
             print(f"Could not save screenshot/source on sort error: {ss_error}")
        return False # Indicate sorting failed
# *** END UPDATED apply_sort_by_newest function ***


# *** UPDATED search_xianyu function with block page check and screenshot delay ***
def search_xianyu(driver, query):
    try:
        search_url = f"https://www.goofish.com/search?q={query}&spm=a21ybx.search.searchInput.0"
        driver.get(search_url)
        time.sleep(random.uniform(4, 8))

        # --- Check for block page ---
        block_page_indicators = ["非法访问", "请使用正常浏览器访问"]
        page_source = driver.page_source
        if any(indicator in page_source for indicator in block_page_indicators):
            block_page_path = os.path.join(BLOCK_SCREENSHOT_DIR, f"block_page_{query.replace(' ', '_')}_{int(time.time())}.png")
            driver.save_screenshot(block_page_path)
            error_msg = f"Block page detected for query '{query}'. Check screenshot: {block_page_path}"
            print(error_msg)
            # Send critical alert to Telegram regardless of debug settings
            telegram_bot.send_message(chat_id=CONFIG["TELEGRAM_CHAT_ID"], text=f"🚨 {error_msg}")
            with open(block_page_path, "rb") as photo:
                telegram_bot.send_photo(chat_id=CONFIG["TELEGRAM_CHAT_ID"], photo=photo, caption=error_msg)
            # Consider stopping the script or waiting a long time here
            # For now, just return empty to skip this query cycle
            return {}
        # --- End block page check ---

        # Apply sorting
        sort_applied = apply_sort_by_newest(driver)

        # Add delay *after* successful sort, *before* extracting products
        if sort_applied:
            print("Waiting 2-3s after sort before extracting...")
            time.sleep(random.uniform(2, 3))
        # --- End screenshot delay ---

        if login_required(driver):
            if handle_login(driver):
                pass
            else:
                log_message(f"Login failed for query '{query}'. Skipping.", level="warning")
                return {}

        if not handle_captcha(driver):
            return {}

        return extract_products(driver, query)

    except TimeoutException:
        log_message(f"Timeout while loading search page for '{query}'. Will retry.", level="warning")
        return {}
    except WebDriverException as e:
        log_message(f"Browser error during search: {str(e)}", level="error")
        return {}
    except Exception as e:
        log_message(f"Error during search: {str(e)}", level="error")
        return {}
# *** END UPDATED search_xianyu function ***


def send_product_alert(product, query, product_id):
    """Sends only the new product alert - not affected by debug flag."""
    try:
        message = f"🆕 New item for '{query}'!\n\n"
        message += f"📌 {product['title']}\n"
        message += f"💰 {product['price']} ({product['price_euro']})\n"
        message += f"🔗 {product['link']}\n"
        message += f"⏰ Found: {product['found_time']}"

        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text=message,
            disable_web_page_preview=False
        )

        screenshot_path = product.get("screenshot_path")
        if screenshot_path and os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as photo:
                telegram_bot.send_photo(
                    chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                    photo=photo
                )
        elif product.get("image"):
             telegram_bot.send_message(
                chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                text=f"Image URL: {product['image']}"
            )

    except Exception as e:
        log_message(f"Error sending product alert: {str(e)}", level="error")

def load_known_products():
    if os.path.exists(KNOWN_PRODUCTS_FILE):
        try:
            with open(KNOWN_PRODUCTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
             print("Error decoding known_products.json. Starting fresh.")
             return {}
        except Exception as e:
            print(f"Error loading known products: {e}")
            return {}
    return {}

def save_known_products(known_products):
    try:
        products_to_save = {}
        for query, items in known_products.items():
             products_to_save[query] = {}
             for item_id, item_data in items.items():
                  data_copy = item_data.copy()
                  data_copy.pop('screenshot_path', None)
                  products_to_save[query][item_id] = data_copy

        with open(KNOWN_PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(products_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving known products: {e}")

def main():
    # Send startup message regardless of debug flag
    telegram_bot.send_message(
        chat_id=CONFIG["TELEGRAM_CHAT_ID"],
        text="🤖 Xianyu product tracker is starting..."
    )

    known_products = load_known_products()

    for query in CONFIG["SEARCH_QUERIES"]:
        if query not in known_products:
            known_products[query] = {}

    driver = None
    try:
        driver = setup_browser()

        cookies_loaded = load_cookies(driver)
        if not cookies_loaded:
            log_message("No saved session found. Will need to login if required by site.")
        else:
             log_message("Cookies loaded successfully.")

        first_run = True

        while True:
            for query in CONFIG["SEARCH_QUERIES"]:
                log_message(f"Checking for items: '{query}'")

                current_products = search_xianyu(driver, query)

                # If search_xianyu returned empty due to block page or other critical error
                if not current_products and not first_run:
                     log_message(f"Skipping product comparison for '{query}' due to earlier error.", level="warning")
                     continue # Move to next query or wait cycle

                if first_run:
                    known_products[query].update(current_products)
                    log_message(f"Initial scan completed for '{query}'. Found {len(current_products)} items.")
                else:
                    new_products = {id: product for id, product in current_products.items()
                                  if id not in known_products[query]}

                    if new_products:
                        telegram_bot.send_message(
                            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                            text=f"Found {len(new_products)} new items for '{query}'!"
                        )

                        for product_id, product in new_products.items():
                            print(f"Waiting 1-2s before sending alert for {product_id}...")
                            time.sleep(random.uniform(1, 2))
                            send_product_alert(product, query, product_id)
                            known_products[query][product_id] = product
                    else:
                        log_message(f"No new items found for '{query}'")

                save_known_products(known_products)

                if len(CONFIG["SEARCH_QUERIES"]) > 1:
                    delay = random.uniform(15, 30)
                    log_message(f"Waiting {int(delay)} seconds before next query...")
                    time.sleep(delay)

            first_run = False

            check_interval = random.randint(CONFIG["CHECK_INTERVAL_MIN"], CONFIG["CHECK_INTERVAL_MAX"])
            log_message(f"Waiting {check_interval//60} minutes and {check_interval % 60} seconds before next check.")
            time.sleep(check_interval)

    except KeyboardInterrupt:
        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text="Bot was manually stopped with Ctrl+C"
        )
    except Exception as e:
        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text=f"CRITICAL ERROR: {str(e)}"
        )
        try:
            if driver:
                error_screenshot_path = os.path.join(ERROR_SCREENSHOT_DIR, "critical_error.png")
                driver.save_screenshot(error_screenshot_path)
                with open(error_screenshot_path, "rb") as photo:
                    telegram_bot.send_photo(
                        chat_id=CONFIG["TELEGRAM_CHAT_ID"],
                        photo=photo,
                        caption="Browser state at critical error"
                    )
        except:
            pass
    finally:
        if driver:
            driver.quit()
        telegram_bot.send_message(
            chat_id=CONFIG["TELEGRAM_CHAT_ID"],
            text="Bot has stopped."
        )

if __name__ == "__main__":
    main()
