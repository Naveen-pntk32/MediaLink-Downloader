# ☁️ 100% Completely FREE Cloud Server Setup (Runs 24/7 When PC is OFF)

This guide provides the exact steps to host your **MediaLink-Downloader Bot** on the cloud **completely free forever** with **NO credit card required**.

---

## 🥇 Recommended: Render.com (100% Free, No Credit Card)

**Render.com** provides a generous Free Tier (750 free compute hours/month, which is enough to run 1 service 24/7 all month). With our built-in health-check server and a free keep-alive ping, your bot will **never sleep and runs 24/7**.

### Step 1: Put Your Code on GitHub
1. Create a free account at [GitHub.com](https://github.com) (if you don't have one).
2. Create a new **Private Repository** named `MediaLink-Downloader`.
3. In your PC terminal (`c:\Automation\MediaLink-Downloader`), push the files:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for MediaLink-Downloader"
   git branch -M main
   git remote add origin https://github.com/<your-username>/MediaLink-Downloader.git
   git push -u origin main
   ```

---

### Step 2: Create a Free Web Service on Render
1. Go to [Render.com](https://render.com) and click **Sign Up** (Sign up with GitHub).
   > *No credit card is required!*
2. On your Render dashboard, click **New +** &rarr; select **Web Service**.
3. Choose **Build and deploy from a Git repository** and connect your `MediaLink-Downloader` repository.
4. Fill in the following details:
   - **Name**: `medialink-downloader-bot` (or any name you like)
   - **Region**: Choose closest to you (e.g., Singapore, Frankfurt, Oregon)
   - **Language / Runtime**: Select **Docker** (Render will use our included `Dockerfile` with FFmpeg pre-installed!)
   - **Instance Type**: Select **Free** ($0/month)
5. Scroll down to **Environment Variables** and click **Add Environment Variable**:
   - **Key**: `TELEGRAM_BOT_TOKEN`
   - **Value**: `Your Telegram Bot Token from @BotFather`
   *(Optional)* If you have allowed user IDs or want to restrict the bot:
   - **Key**: `ALLOWED_USER_IDS`
   - **Value**: `your_telegram_user_id`
6. Click **Deploy Web Service** at the bottom.
   - Render will build your Docker container, install FFmpeg and Python dependencies, and start `bot.py`!
   - In 2–3 minutes, you will see `==> Your service is live 🎉`.
   - Copy your service URL from the top of the page:
     `https://medialink-downloader-bot.onrender.com`

---

### Step 3: Keep It Running 24/7 (Prevent Render Sleep)
Render's free tier sleeps if no web request is received for 15 minutes. We set up a free automated ping so it stays awake 24/7 forever:

1. Go to [cron-job.org](https://cron-job.org) (100% free forever, no credit card) or [UptimeRobot.com](https://uptimerobot.com).
2. Create a free account.
3. Click **Create Cronjob**:
   - **Title**: `MediaLink Bot Keep-Alive`
   - **URL**: Paste your Render URL: `https://medialink-downloader-bot.onrender.com/`
   - **Execution schedule**: Every **10 minutes**
4. Click **Create**.
5. **Done!** Every 10 minutes, cron-job.org pings your bot's health check server. The bot will **never shut down**, running 24/7 even when your PC is turned off!

---

## 🥈 Alternative: Koyeb (100% Free Eco Tier, No Credit Card)

**Koyeb** is another platform offering a 100% free Eco Service that does not sleep:

1. Sign up at [Koyeb.com](https://www.koyeb.com) (Log in with GitHub).
2. Click **Create App**.
3. Select **GitHub** as the deployment method and choose your `MediaLink-Downloader` repo.
4. Select **Dockerfile** builder.
5. In **Instance Type**, select **Eco** (Free).
6. Under **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN` = `your_token_from_botfather`
7. Click **Deploy**. Koyeb runs your bot in the cloud 24/7 at $0.00!

---

## 🥉 Alternative: Oracle Cloud "Always Free" VPS (For Advanced Users)

If you want a full, dedicated Ubuntu Linux virtual machine:
1. Go to [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/).
2. Create an **"Always Free"** Compute Instance (VM.Standard.A1.Flex or VM.Standard.E2.1.Micro).
   *(Requires a debit/credit card for $0 identity verification, but is 100% free forever).*
3. SSH into the server and run:
   ```bash
   git clone <your-repo>
   cd MediaLink-Downloader
   cp .env.example .env
   # Add your TELEGRAM_BOT_TOKEN to .env
   docker compose up -d --build
   ```
4. It will run 24/7 in your personal cloud server forever without needing any keep-alive pings.

---

## 📱 How to Use When Your PC Is Off

Once your bot is deployed on Render or Koyeb:
1. Turn your PC completely off.
2. Open Telegram on your smartphone.
3. Send any Instagram Reel, Post, or YouTube link to your bot.
4. Tap **"📱 Send to Chat (MP4 Video)"**.
5. The cloud server downloads the video and sends the file directly into your Telegram chat!
