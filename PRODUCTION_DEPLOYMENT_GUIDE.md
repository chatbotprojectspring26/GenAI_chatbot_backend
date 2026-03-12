# 🚀 GenAI Research Chatbot: Complete System Deployment & Testing Guide

This document explains exactly how the three main pieces of our platform—the **React Frontend**, the **FastAPI Backend**, and the **MongoDB Database**—connect, how they are deployed, and how to test them end-to-end to ensure the system is working perfectly for research participants.

---

## 🏗️ System Architecture Overview

1. **Frontend (Vercel)**: A React application built by the frontend team. It hosts the UI where users type their messages. It is responsible for reading the Qualtrics URL parameters, assigning the A/B condition, and sending all data to the backend API.
2. **Backend (Railway)**: A Python FastAPI application (built by you). It handles the heavy lifting: receiving chat messages from the frontend, talking to the OpenAI `gpt-4o-mini` model, and saving all session data (messages, events, and focus tracking) to the database.
3. **Database (MongoDB Atlas)**: A cloud database that securely stores all the data the backend receives.

---

## 🌐 1. Deploying the Frontend (Vercel)

The frontend team manages the React deployment on Vercel. Whenever they push code to their GitHub repo, Vercel automatically builds and hosts the site.

**Crucial Step: Environment Variables**
For the frontend to know how to talk to your backend, the frontend team **must** configure the following Environment Variable inside their Vercel Project Settings:

*   `REACT_APP_API_URL` (or whatever variable their code uses) = `https://chatbotdesign2026backend-production.up.railway.app`

Without this, the React app will try to send messages to `localhost:8000` and it will crash for live users.

---

## 🚂 2. Deploying the Backend (Railway)

Your backend is fully deployed on Railway. It automatically pulls from the `merged-frontend-backend` branch on your GitHub repository.

**Backend Environment Variables (Railway):**
You have already configured these in Railway, but if you ever need to change keys, go to **Railway Dashboard → Variables**:
*   `MONGODB_URI` = `mongodb+srv://...` (Your Atlas Connection String)
*   `MONGODB_DB_NAME` = `chatbot_research`
*   `OPENAI_API_KEY` = `sk-proj-...`
*   `OPENAI_MODEL` = `gpt-4o-mini`
*   `CORS_ORIGINS` = `https://<YOUR_FRONTEND_VERCEL_URL>.vercel.app` *(Must match the exact URL the frontend team is using so their requests aren't blocked)*

---

## 🗄️ 3. Database Access (MongoDB Atlas)

Because your backend lives on the cloud in Railway, Railway's IP address needs permission to read/write to your MongoDB Atlas database.

**How to verify Database Access is open:**
1. Log into MongoDB Atlas.
2. Click **Network Access** on the left menu.
3. Ensure you have an entry for `0.0.0.0/0` (Allow Access from Anywhere).
4. If this is missing, Railway will instantly fail its "Healthcheck" because it cannot connect to the DB.

---

## 🧪 4. How to Test End-to-End (The Full Flow)

Once Vercel is live and Railway is green (Healthy), you need to verify the whole system works together.

### Step 1: Simulate a user arriving from Qualtrics
In production, Qualtrics will send users to the Vercel frontend with special URL parameters. To test this yourself, open your browser and go to the Vercel frontend URL, manually attaching the parameters.

Example URL:
`https://<YOUR_FRONTEND_VERCEL_URL>.vercel.app?pid=test_user_001&condition=control`

### Step 2: Verify the Session Started
When that page loads, the Frontend will invisibly send a `POST /session/start` request to your Railway backend:
```json
{
  "pid": "test_user_001",
  "condition_name": "control"
}
```
**Check MongoDB:** Open MongoDB Atlas, look inside the `chat_sessions` collection, and verify a new session was created for `test_user_001`.

### Step 3: Test the Chatbot (OpenAI)
Type "Hello, what are the instructions?" into the React chat box and press Send.
1. The frontend sends `POST /chat` to Railway.
2. Railway takes the message, asks OpenAI `gpt-4o-mini` for an answer, saves both messages to MongoDB, and replies to the frontend.
3. You should see Kavya (the assistant) reply in your browser within 3-5 seconds.

**Check MongoDB:** Look inside the `messages` collection. You should see two new documents: your "Hello" constraint, and the Assistant's reply.

### Step 4: Test Tab Tracking (The New Feature)
Click open a new tab in your browser (leaving the chatbot tab hidden), wait 5 seconds, and then click back into the chatbot.
1. The frontend should detect this and send a `POST /session/tab-event` request to Railway.

**Check MongoDB:** Look inside the `tab_events` collection. You should see a document recording exactly how long you left the window!

### Step 5: End the Session
Click the "Finish" or "Submit" button on the React frontend.
1. The frontend sends `POST /session/end` to Railway.
2. Railway marks the session as `completed` in the database and returns a Qualtrics Redirect URL.
3. The frontend should automatically redirect your browser back to Qualtrics.

---

### 🎉 If all 5 steps work, your platform is 100% ready for live research participants!
