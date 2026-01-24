# Deployment Instructions

I've configured the project for Railway deployment, but the final linking step requires your authentication.

Please run the following commands in your terminal:

## 1. Deploy Backend

```bash
cd backend
railway link
# Select the project "onco-ttt-full"
# If prompted for a service, select "Create a new Service" -> name it "backend"
# OR if "backend" exists, select it.

railway up
```

## 2. Deploy Frontend

```bash
cd ../frontend
railway link
# Select the project "onco-ttt-full"
# If prompted for a service, select "Create a new Service" -> name it "frontend"
# OR if "frontend" exists, select it.

# Set the backend URL (replace with your actual backend URL from step 1)
railway variables --set "NEXT_PUBLIC_API_URL=https://<YOUR_BACKEND_URL>.up.railway.app"

railway up
```

## 3. Verify
Open the frontend URL provided by Railway after the deployment finishes.
