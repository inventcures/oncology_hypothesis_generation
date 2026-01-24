# Deployment Guide for Onco-TTT

The project is configured for Railway deployment.

## 1. Backend Status
- Project Created: **onco-ttt-full**
- Deployment attempted.
- URL (Estimated): `https://onco-ttt-full-production.up.railway.app`
- **Verify:** Check your Railway Dashboard. If the backend service is running, copy its public domain.

## 2. Frontend Deployment (Manual Steps)
Since the CLI requires interactive authentication for linking new services, please run the following in your terminal:

1. **Navigate to Frontend:**
   ```bash
   cd frontend
   ```

2. **Link to the Project:**
   ```bash
   railway link
   ```
   *Select "onco-ttt-full" from the list.*

3. **Set Backend URL:**
   Replace `<BACKEND_URL>` with the actual URL from Step 1 (e.g., `https://onco-ttt-full-production.up.railway.app`).
   ```bash
   railway variables --set "NEXT_PUBLIC_API_URL=<BACKEND_URL>"
   ```

4. **Deploy:**
   ```bash
   railway service --create frontend  # If prompted/needed
   railway up
   ```

5. **Access:**
   Once deployed, Railway will provide a Frontend URL (e.g., `https://frontend-production.up.railway.app`). Open this in your browser.

## Troubleshooting
- If the Backend 404s, check the "Deploy Logs" in Railway. Ensure `uvicorn` started successfully.
- If Frontend can't connect, ensure the `NEXT_PUBLIC_API_URL` does NOT have a trailing slash (e.g., `.../app`, not `.../app/`).
