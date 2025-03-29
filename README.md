# Xianyu/Goofish Product Monitor Bot

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

This Python script automatically monitors search results on Xianyu/Goofish (Taobao's secondhand marketplace) for specified products and notifies you via Telegram when new items are found.

## Core Functionality

*   **Automated Monitoring:** Periodically searches Xianyu/Goofish for your defined search queries.
*   **Real-time Alerts:** Sends notifications to a specified Telegram chat when a new listing appears on the first page of results (after attempting to sort by newest).
*   **Price Conversion:** Includes both the original CNY price and an automatic conversion to EUR (using an external API, with fallback).
*   **Visual Confirmation:** Takes screenshots of new items and includes them in the Telegram alert.
*   **Session Persistence:** Uses cookies (`data/xianyu_cookies.json`) to maintain login sessions between runs, reducing the need for frequent QR code scans.
*   **Captcha Handling:**
    *   Attempts automated solving of slider captchas using the Anti-Captcha service.
    *   Falls back to interactive remote solving via Telegram if automated solving fails or isn't configured.
*   **Configurable:** Search terms, check intervals, API keys, and behavior are easily configured via `config.json`.
*   **Organized Output:** Saves screenshots and logs into structured directories (`screenshots/`, `logs/`, `data/`).

## Key Features Implemented

*   Loads configuration from `config.json`.
*   Creates necessary directories (`data`, `screenshots/*`, `logs/*`).
*   Uses `undetected-chromedriver` to reduce bot detection.
*   Attempts to sort search results by "Latest" (`最新`) using JavaScript clicks to improve chances of finding new items on the first page.
*   Handles login via Xianyu QR code sent to Telegram.
*   Detects potential block pages ("非法访问") and alerts the user.
*   Extracts product details (title, price, link, image) from search results using robust selectors.
*   Compares found items against a local database (`data/known_products.json`) to identify new listings.
*   Sends detailed Telegram alerts for new items, including price conversion and item screenshot.
*   Includes optional debug messaging to Telegram, controlled via `config.json`.
*   Randomized check intervals to reduce predictability.

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
4.  **Configure `config.json`:**
    *   Create a file named `config.json` in the same directory as `monitoring.py`.
    *   Copy the following template and **replace the placeholder values** with your actual information or use the downloaded file:
        ```json
        {
          "SEARCH_QUERIES": ["your search term 1", "your search term 2"],
          "CHECK_INTERVAL_MIN": 540,
          "CHECK_INTERVAL_MAX": 850,
          "ANTICAPTCHA_KEY": "YOUR_ANTICAPTCHA_KEY_HERE",
          "TELEGRAM_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
          "TELEGRAM_CHAT_ID": "YOUR_TELEGRAM_CHAT_ID_HERE",
          "SEND_DEBUG_MESSAGES": true,
          "HEADLESS": false,
          "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        ```
    *   **`SEARCH_QUERIES`**: List of product names to search for.
    *   **`CHECK_INTERVAL_MIN`/`MAX`**: Minimum and maximum time (in seconds) between full search cycles. A random value in this range is chosen each time.
    *   **`ANTICAPTCHA_KEY`**: Your API key from [Anti-Captcha.com](https://anti-captcha.com/) (optional, needed for automated captcha solving).
    *   **`TELEGRAM_TOKEN`**: Your Telegram Bot token obtained from BotFather.
    *   **`TELEGRAM_CHAT_ID`**: The ID of the Telegram chat where notifications should be sent. You can get this from bots like `@userinfobot`.
    *   **`SEND_DEBUG_MESSAGES`**: Set to `true` to receive status/error messages, or `false` to only receive new product alerts and critical errors.
    *   **`HEADLESS`**: **MUST BE `false`**. Xianyu/Goofish detects and blocks headless browsers.
    *   **`USER_AGENT`**: The User-Agent string the browser should use.

## Usage

1.  **Ensure GUI Environment:** This script **requires a graphical desktop environment** to run Chrome non-headless. It will **not** work on headless servers like standard Linux VPS setups without a desktop, PythonAnywhere, Replit basic tiers, etc. You need to run it on:
    *   Your local machine (if left on 24/7).
    *   A Windows VPS (connected via RDP).
    *   A Linux VPS with a desktop environment (XFCE, LXDE) and VNC/xRDP installed.
    *   A dedicated physical machine (e.g., an old laptop, Raspberry Pi 4 *with sufficient RAM and desktop installed*).
2.  **Run the Script:**
    ```bash
    python monitoring.py
    ```
3.  **First Run & Login:**
    *   The script will likely detect no saved session and state that login is required.
    *   It will navigate to the Xianyu login page (or encounter a login prompt) and send a QR code to your configured Telegram chat.
    *   Scan this QR code using your **Xianyu mobile app** (not Taobao) to log in.
    *   Once login is successful, cookies will be saved to `data/xianyu_cookies.json`.
    *   The first scan for each query populates the `data/known_products.json` database without sending alerts.
4.  **Subsequent Runs:**
    *   The script will load cookies to try and maintain the session.
    *   It will periodically run searches, attempt to sort by newest, scrape the first page, and compare found items to the known products database.
    *   If new items are found, alerts will be sent to Telegram.
    *   If captchas are encountered, it will attempt automated solving or prompt you via Telegram.
    *   If the block page is detected, it will send an alert and skip the current cycle for that query.

## Known Issues & Limitations

*   **Headless Detection:** Xianyu/Goofish actively detects and blocks headless browser automation. **You MUST run this script with `"HEADLESS": false` in a graphical environment.**
*   **Sorting Instability:** The automated clicking of the "Sort by Latest" buttons is complex and has proven unreliable during development. It may fail due to timeouts or elements not being interactable. If sorting fails, the script logs a warning and proceeds to scrape the results using the default sort order, which may cause new items *not* on the first page to be missed.
*   **First Page Only:** The script only scrapes items appearing on the *first page* of search results, even after attempting to sort. New items listed on subsequent pages will not be detected.
*   **Captcha Solving:**
    *   Automated solving uses Anti-Captcha's image-to-text, which is not ideal for slider captchas and may have a low success rate.
    *   Manual solving via Telegram requires user interaction and potentially trial-and-error with slider percentages.
*   **Dynamic Website:** Xianyu/Goofish can change its website structure (HTML, CSS classes) at any time, which may break the sorting or item scraping logic, requiring updates to the selectors in the script.
*   **Block Page:** If Xianyu detects the bot for other reasons (e.g., too frequent requests, IP reputation), it may display a block page ("非法访问"), which the script attempts to detect. This usually requires stopping the bot, potentially changing IP (if possible), and trying again later.

## Potential Future Improvements

*   Implement pagination or infinite scrolling to monitor more than just the first page.
*   Integrate a more specialized captcha solving service designed for sliders.
*   Add proxy support (especially rotating residential proxies) to mitigate IP blocking.
*   Implement more sophisticated anti-detection techniques.
*   Add more robust error handling and retry logic.
*   Create a simple UI for configuration instead of editing `config.json`.
*   Figure out how to set it up headless without Xianyu/Goofish blocking the instance.

## License

Copyright (c) 2025 Microck - All Rights Reserved

This project is provided under a custom license. Please see the `LICENSE` file for details.

**Key restrictions include:**
*   Use and modification are permitted for **personal, non-commercial purposes only**.
*   **Redistribution** of the software (modified or unmodified) is **prohibited**.
*   **Selling** or sublicensing the software is **prohibited**.
*   Use for **any commercial purpose** is **prohibited**.

Refer to the full `LICENSE` file for the complete terms.

