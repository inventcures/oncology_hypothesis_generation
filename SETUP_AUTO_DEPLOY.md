# Setting up Automatic Deployments (GitHub Integration)

Currently, we are deploying manually using the Railway CLI (`railway up`). To enable automatic deployments whenever you push to GitHub, follow these steps in the Railway Dashboard:

1. **Open your Project:**
   Go to [Railway Dashboard](https://railway.com/dashboard) and open **onco-ttt-full**.

2. **Connect GitHub Repo:**
   - Click on the **backend** service card.
   - Go to **Settings** -> **Git**.
   - Click **Connect Repo**.
   - Select `inventcures/oncology_hypothesis_generation`.
   - **Important:** Set the **Root Directory** to `/backend`.

3. **Repeat for Frontend:**
   - Click on the **frontend** service card.
   - Go to **Settings** -> **Git**.
   - Click **Connect Repo**.
   - Select the *same* repo: `inventcures/oncology_hypothesis_generation`.
   - **Important:** Set the **Root Directory** to `/frontend`.

4. **Done!**
   Now, every time you run `git push origin main`, Railway will detect the changes in the respective folders and trigger a new deployment automatically.
