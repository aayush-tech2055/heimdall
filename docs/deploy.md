# Deploying Heimdall (task 10.1)

| Part | Where | Notes |
|---|---|---|
| Database, Auth, Storage | Supabase (already live) | nothing to do |
| Backend (FastAPI) | Render, free plan, Docker (`backend/Dockerfile`, `render.yaml`) | includes FFmpeg (video) and Presidio with the small spaCy model |
| Frontend (Next.js) | Vercel, root folder `frontend` | |
| Demo websites | GitHub Pages (`.github/workflows/demo-site.yml`) | |

All values below come from `backend/.env` and `frontend/.env.local` on the developer's machine.
Never paste them into the repository.

## 1. Backend on Render

1. Sign in at https://dashboard.render.com with GitHub and allow access to the `heimdall` repo.
2. **New → Blueprint**, pick the `heimdall` repo, branch `main`. Render reads `render.yaml`.
3. It asks for the secret values. Copy each from `backend/.env`:
   `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.
   (`SUPABASE_JWT_SECRET` is not needed: sign-in tokens are checked against Supabase's public
   keys.) For `CORS_ORIGINS` enter `http://localhost:3000` for now (changed in step 3).
4. **Apply**. The first build takes 5–10 minutes. When it is live, open
   `https://<service>.onrender.com/health`; it must show `{"status":"ok",...}`. Copy that base URL.

If the logs show the instance running out of memory, set `WITH_PRIVACY` to `false` in the
Dockerfile's `ARG` line (or upgrade the plan) and redeploy. Pattern masking (emails, phones, IDs, card numbers,
confidential terms) keeps working; only names and places are no longer detected.

## 2. Frontend on Vercel

1. Sign in at https://vercel.com with GitHub. **Add New → Project**, import `heimdall`.
2. **Root Directory**: `frontend`. Framework: Next.js (detected).
3. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = the Render URL from step 1 (no trailing slash)
   - `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` = from `frontend/.env.local`
4. **Deploy**. Copy the production URL, for example `https://heimdall-xyz.vercel.app`.

## 3. Connect them

1. Render → the service → **Environment** → set `CORS_ORIGINS` to the Vercel URL (no trailing
   slash; several URLs can be comma-separated) → **Save, rebuild and deploy**.
2. Supabase → **Authentication → URL Configuration** → **Site URL** = the Vercel URL.

## 4. Check

Open the Vercel URL, sign in as `admin@acmelearn.example`, open Guidelines (rules load), then as
`creator@acmelearn.example` paste a short text and check it. On the free plan the backend sleeps
after 15 minutes without traffic, so the first request after a pause takes about a minute; open
`/health` a minute before a demo.
