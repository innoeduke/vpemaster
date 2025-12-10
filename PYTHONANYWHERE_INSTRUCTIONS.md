# Deploying Fix to PythonAnywhere

Since you cannot run the script directly from here, you need to execute the following steps on your PythonAnywhere account.

## 1. Update Code on Server
Open a **Bash console** on PythonAnywhere and navigate to your project folder. Pull your latest changes (ensure you have committed and pushed your local changes first):

```bash
cd ~/your-project-folder  # Adjust path as necessary
git pull
```

## 2. Run the Fix Script
In the same console, run the password reset script to fix the database entries on the server:

```bash
python fix_password.py
```
*Note: Ensure your virtual environment is activated if you use one (e.g., `workon myenv`).*

## 3. Reload Web App
Go to the **Web** tab in your PythonAnywhere dashboard and click the green **Reload** button to apply the code changes.

## 4. Verify
Try logging in to your live site with the username `admin` (or your user) and password `leadership`.
