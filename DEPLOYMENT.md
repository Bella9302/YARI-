# Getting YARI Lifestyle running

There are two stages:

1. **Run it on your own computer** to try everything out. Only you can see it.
2. **Put it online** so customers, sellers and representatives can use it from their phones.

You don't need to be a programmer. You will copy and paste a few commands.

---

## Stage 1: run it on your computer

### 1. Install Python

Download Python 3.11 or newer from <https://www.python.org/downloads/> and install it.

- **Windows:** on the first install screen, tick **"Add python.exe to PATH"** before clicking Install.
- **Mac:** run the installer with the default options.

### 2. Download the store

1. Open <https://github.com/Bella9302/YARI->.
2. Click the green **Code** button, then **Download ZIP**.
3. Unzip it somewhere easy to find, such as your Desktop.

### 3. Open a terminal in that folder

- **Windows:** open the unzipped folder in File Explorer. Click the address bar at the top, type `cmd`, and press Enter.
- **Mac:** right-click the unzipped folder and choose **Services → New Terminal at Folder**.
  If you don't see that option, open Terminal, type `cd ` (with a space), drag the folder into the window, and press Enter.

### 4. Install and start

Copy these lines one at a time and press Enter after each.

**Windows**

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask --app app seed
python run.py
```

**Mac**

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app seed
python run.py
```

The `seed` line fills the store with demo products and demo accounts so you can explore.

### 5. Open the store

Go to <http://localhost:5000> in your browser.

Log in at <http://localhost:5000/account/login> with any of these. The password for all of them is `password123`.

| Role | Email |
|------|-------|
| Owner | owner@yari.co.za |
| Seller | naledi@yari.co.za |
| Sales representative | lerato@yari.co.za |

A good first test: place an order as a customer using the rep code `YR-LER01`. Then log in as the owner and send it to a seller. Log in as that seller and mark it shipped. Finally, log in as the rep and confirm payment.

### Try it on your phone

Your phone must be on the same Wi-Fi as your computer.
When you ran `python run.py`, the terminal printed two addresses.
Type the one that starts with `192.168.` or `10.` into your phone's browser.
On Windows, click **Allow** if a firewall message appears.

### Stopping and starting again

- To stop the store, click the terminal and press **Ctrl + C**.
- To start it again later, open a terminal in the folder. Run the second line from step 4 (the one with `activate`), then `python run.py`.

### Start with an empty store instead of demo data

Stop the store, delete the file `instance/yari.sqlite`, then run:

```
flask --app app create-owner
```

It asks for your name, email and a password. Start the store again and log in with those details.

---

## Stage 2: put it online (free, with PythonAnywhere)

PythonAnywhere is recommended because its free plan keeps your orders, accounts and product photos saved permanently.
Many other free hosts wipe saved data every time they restart.

Your store's address will be `https://YOURNAME.pythonanywhere.com`.
In the steps below, replace **YOURNAME** with the username you choose.

### 1. Create an account

Sign up for a free **Beginner** account at <https://www.pythonanywhere.com>.
Pick your username carefully, because it becomes your web address.

### 2. Download the store onto PythonAnywhere

From your PythonAnywhere dashboard, open a new **Bash** console and paste these lines one at a time:

```
git clone https://github.com/Bella9302/YARI-.git yari
cd yari
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app create-owner
```

The last command asks for your name, email and password. That becomes your owner login.

If you'd rather launch with the demo products and edit them, also run `flask --app app seed`.
Change or deactivate the demo accounts afterwards, because their password is public.

### 3. Create the web app

1. Open the **Web** tab and click **Add a new web app**. Click **Next**.
2. Choose **Manual configuration**, not the "Flask" option.
3. Choose **Python 3.11**, the same version used in step 2. Click **Next**.

### 4. Point it at the store

On the page that opens, fill in these settings.

**Code section**

- **Source code:** `/home/YOURNAME/yari`

**Virtualenv section**

- Enter `/home/YOURNAME/yari/.venv`

**WSGI configuration file**

Click the link to open the file. Delete everything in it, then paste this and fill in your own details:

```python
import os
import sys

path = "/home/YOURNAME/yari"
if path not in sys.path:
    sys.path.insert(0, path)

# Your business details, shown on the website
os.environ["BUSINESS_EMAIL"] = "hello@yourbusiness.co.za"
os.environ["BUSINESS_PHONE"] = "+27 82 000 0000"
os.environ["BUSINESS_WHATSAPP"] = "27820000000"   # country code + number, no spaces or +
os.environ["BUSINESS_ADDRESS"] = "Johannesburg, South Africa"

from wsgi import app as application
```

Click **Save**.

**Static files section** (makes images load faster)

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/YOURNAME/yari/app/static/` |

**Security section**

Turn on **Force HTTPS**.

### 5. Go live

Click the green **Reload** button at the top of the Web tab.
Then visit `https://YOURNAME.pythonanywhere.com`.

Log in at `https://YOURNAME.pythonanywhere.com/account/login` with the owner details you created.
From the owner portal you can:

- add categories and products
- create accounts for your sellers and sales representatives

Each representative gets their own unique code automatically.

### Keep it running

On the free plan, the site switches off after three months unless you extend it.
Log in to PythonAnywhere at least once every three months and click **Run until 3 months from today** on the Web tab.
PythonAnywhere emails you a reminder before it expires.

### Back up your data

Everything (orders, accounts, products) is in one file: `yari/instance/yari.sqlite`.
Download it from the **Files** tab now and then to keep a copy.

### Getting updates

When the code on GitHub changes, open a Bash console and run:

```
cd ~/yari
git pull
source .venv/bin/activate
pip install -r requirements.txt
```

Then click **Reload** on the Web tab.

---

## When you outgrow the free plan

- **Your own domain** such as `yarilifestyle.co.za` needs a paid PythonAnywhere plan. After upgrading, add the domain on the Web tab and follow their instructions to update your domain's DNS.
- **Other hosts** such as Render or Railway also work: the start command is `gunicorn wsgi:app`.
  Their free tiers don't keep files, so you would need a paid persistent disk for the `instance/` and `app/static/uploads/` folders.
- **Online card payments** need a payment provider account, for example PayFast, Yoco or Ozow. The code has one clearly marked place for it; see the README.

## If something goes wrong

| What you see | What to do |
|--------------|-----------|
| `'python' is not recognized` or `command not found` on Windows | Reinstall Python and tick "Add python.exe to PATH". Or use `py` instead of `python`. |
| `No module named flask` | Run the `activate` line again, then `pip install -r requirements.txt`. |
| "Something went wrong" page on PythonAnywhere | On the Web tab, open the **error log** link. The last lines say what failed. Most often the path or YOURNAME in the WSGI file has a typo. |
| Forgot the owner password | In a console in the `yari` folder, run the `activate` line, then `flask --app app create-owner` with a new email. Log in with it and reset the old account under **Sellers & reps**. |
| "The form has expired" | Refresh the page and submit again. This protects forms from being submitted by other websites. |
