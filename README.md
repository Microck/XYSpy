# Xianyu/Goofish Product Monitor Bot

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

This Python script automatically monitors search results on Xianyu/Goofish (Taobao's secondhand marketplace) for specified products and notifies you via Telegram when new items are found.

## Core Functionality

*   **Automated Monitoring:** Periodically searches Xianyu/Goofish for queries listed in `search_queries.txt`.
*   **Real-time Alerts:** Sends notifications to a specified Telegram chat when a new listing appears on the first page of results (after attempting to sort by newest).
*   **Price Conversion:** Includes both the original CNY price and an automatic conversion to EUR (using an external API, with fallback).
*   **Visual Confirmation:** Takes screenshots of new items and includes them in the Telegram alert.
*   **Session Persistence:** Uses cookies (`data/xianyu_cookies.json`) to maintain login sessions between runs.
*   **Captcha Handling (Optional):**
    *   Attempts automated solving of slider captchas using the Anti-Captcha service (if API key is provided).
    *   Falls back to interactive remote solving via Telegram if automated solving fails or no API key is configured. Captchas may not always appear.
*   **Login Prompt Handling:** Detects intermittent login prompts, skips the affected search cycle by default, but requests a QR code login via Telegram if prompts become too frequent.
*   **Configurable:** API keys, chat ID, intervals, and behavior are configured via `config.json`. Search terms are managed in `search_queries.txt`.
*   **Organized Output:** Saves cookies, known products, screenshots, and logs into structured directories (`data/`, `screenshots/`, `logs/`).

## Key Features Implemented

*   Loads configuration from `config.json`.
*   Loads search queries from `search_queries.txt`.
*   Creates necessary directories (`data`, `screenshots/*`, `logs/*`).
*   Uses `undetected-chromedriver` to reduce bot detection.
*   **Mandatory Sorting:** Attempts to sort search results by "Latest" (`最新`). If sorting fails, the script skips processing that query for the current cycle to avoid errors.
*   Handles login via Xianyu QR code sent to Telegram, with rate-limiting logic for intermittent prompts.
*   Detects potential block pages ("非法访问") and alerts the user.
*   Extracts product details (title, price, link, image) from search results using robust selectors.
*   Compares found items against a local database (`data/known_products.json`) to identify new listings.
*   Sends detailed Telegram alerts for new items, including price conversion and item screenshot.
*   Includes optional debug messaging to Telegram, controlled via `config.json`.
*   Randomized check intervals to reduce predictability.
*   Adds a short delay after sorting before scraping items.

## Requirements

*   **Python 3.9+**
*   **Google Chrome** browser installed.
*   **Required Python Libraries:** Install using pip:
    ```bash
    pip install -r requirements.txt
    ```
    The `requirements.txt` file should contain:
    ```
    requests
    selenium
    undetected-chromedriver
    webdriver-manager
    python-telegram-bot
    anticaptchaofficial
    ```

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Microck/XYSpy
    cd XYSpy
    ```
2.  **Install Python Requirements:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Install ChromeDriver:** The `webdriver-manager` library *should* handle this automatically the first time Selenium needs it. If you encounter issues, you might need to manually download ChromeDriver matching your installed Chrome version and ensure it's in your system's PATH or specify its path.
4.  **Create `search_queries.txt`:**
    *   Create a file named `search_queries.txt` in the same directory as `monitoring.py`.
    *   Add your desired search terms to this file, **one query per line**. Example:
        ```
        mechanical keyboard
        metallica tshirt
        anime figurine
        ```
5.  **Configure `config.json`:**
    *   Create a file named `config.json` in the same directory as `monitoring.py`.
    *   Copy the following template and **replace the placeholder values** with your actual information:
        ```json
        {
          "CHECK_INTERVAL_MIN": 540,
          "CHECK_INTERVAL_MAX": 850,
          "ANTICAPTCHA_KEY": "YOUR_ANTICAPTCHA_KEY_HERE_OR_LEAVE_EMPTY",
          "TELEGRAM_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
          "TELEGRAM_CHAT_ID": "YOUR_TELEGRAM_CHAT_ID_HERE",
          "SEND_DEBUG_MESSAGES": true,
          "HEADLESS": false,
          "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        ```
    *   **`CHECK_INTERVAL_MIN`/`MAX`**: Minimum and maximum time (in seconds) between full search cycles.
    *   **`ANTICAPTCHA_KEY`**: **Optional.** Your API key from [Anti-Captcha.com](https://anti-captcha.com/). If left empty (`""`), automated captcha solving will be skipped, and you will always be prompted via Telegram if a captcha appears.
    *   **`TELEGRAM_TOKEN`**: Your Telegram Bot token obtained from BotFather.
    *   **`TELEGRAM_CHAT_ID`**: The ID of the Telegram chat where notifications should be sent.
    *   **`SEND_DEBUG_MESSAGES`**: Set to `true` to receive status/error messages, or `false` to only receive new product alerts and critical errors.
    *   **`HEADLESS`**: **MUST BE `false`**. Xianyu/Goofish detects and blocks headless browsers.
    *   **`USER_AGENT`**: The User-Agent string the browser should use.

## Usage

1.  **Ensure GUI Environment:** This script **requires a graphical desktop environment** to run Chrome non-headless. It will **not** work on headless servers like standard Linux VPS setups without a desktop, PythonAnywhere, Replit basic tiers, etc. Use a local machine, Windows VPS (RDP), Linux VPS with Desktop+VNC/xRDP, or a dedicated physical machine.
2.  **Run the Script:**
    ```bash
    python monitoring.py
    ```
3.  **First Run & Login:**
    *   The script will likely detect no saved session.
    *   If the site requires login immediately or frequently, it will send a QR code to Telegram.
    *   Scan this QR code using your **Xianyu mobile app**.
    *   Successful login saves cookies to `data/xianyu_cookies.json`.
    *   The first scan populates `data/known_products.json` without sending alerts.
4.  **Subsequent Runs:**
    *   Loads cookies to maintain session.
    *   Periodically runs searches for queries in `search_queries.txt`.
    *   Detects intermittent login prompts and skips the cycle unless they become too frequent (then prompts for QR login).
    *   Attempts to sort by newest. **If sorting fails, the query is skipped for that cycle.**
    *   Scrapes the first page (if sorted successfully).
    *   Compares found items to the database.
    *   Sends alerts for new items.
    *   Handles captchas (automated attempt if key provided, otherwise manual prompt).
    *   Detects and alerts about block pages.

## Known Issues & Limitations

*   **Headless Detection:** Xianyu/Goofish actively detects and blocks headless browser automation. **You MUST run this script with `"HEADLESS": false` in a graphical environment.**
*   **Sorting Instability:** Clicking the "Sort by Latest" buttons can still fail intermittently due to timing or anti-bot measures. The script now skips the query cycle if sorting fails, preventing errors but potentially delaying detection if the failure coincides with a new item appearing.
*   **First Page Only:** Only scrapes items on the first page of results.
*   **Captcha Solving:** Automated solving via Anti-Captcha is unreliable for sliders. Manual solving requires user interaction. Captchas might not appear frequently.
*   **Dynamic Website:** Future changes to Xianyu/Goofish's structure may break selectors.
*   **Block Page:** Detection by Xianyu can lead to a block page, requiring manual intervention (stopping the bot, potentially changing IP).

## Potential Future Improvements

*   Implement pagination or infinite scrolling.
*   Integrate a better captcha solving service.
*   Add proxy support.
*   Implement more sophisticated anti-detection techniques.
*   Add more robust error handling and retry logic.
*   Create a simple UI for configuration.
*   Investigate reliable methods for headless operation (currently seems infeasible).

## License

Copyright (c) 2025 Microck - All Rights Reserved

This project is provided under a custom license. Please see the `LICENSE` file for details.

**Key restrictions include:**
*   Use and modification are permitted for **personal, non-commercial purposes only**.
*   **Redistribution** of the software (modified or unmodified) is **prohibited**.
*   **Selling** or sublicensing the software is **prohibited**.
*   Use for **any commercial purpose** is **prohibited**.

Refer to the full `LICENSE` file for the complete terms.
