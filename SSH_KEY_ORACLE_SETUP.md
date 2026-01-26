# How to Add SSH Key to Oracle Cloud Instance

## METHOD 1: Edit Instance SSH Keys (Most Common)

**Step 1:** Go to Oracle Cloud Console
- URL: https://cloud.oracle.com/
- Login with your account

**Step 2:** Find your instance
- Click the **hamburger menu** (3 lines, top-left)
- Click **Compute** 
- Click **Instances**
- **Click the name** of your instance (look for algo-trading-bot or similar)

**Step 3:** Look for SSH Keys section
- Scroll down on the instance details page
- Find the section labeled **"SSH Keys"** or **"Public SSH Keys"**
- You should see your current key listed

**Step 4:** If you see an "Edit" or "Add" button
- Click **Edit** or **Add SSH Key**
- Paste your new public key:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMgHJn40Br+/ksYxmRood/A3rQVFAq8kHQqgOvLDL6uq ronald mcdonald@DESKTOP-5313
```
- Click **Save**
- Wait 30 seconds

---

## METHOD 2: Can't Find It? Try This Alternative

If you don't see an "Edit" button or SSH Keys section, try this:

**Step 1:** On the same instance page, look for a menu (three dots ⋯)
- Top right corner of the instance details
- Click it

**Step 2:** Look for options like:
- "Edit Instance"
- "Instance Settings"
- "Metadata"

**Step 3:** If you see "Instance Metadata":
- Click it
- Look for "Custom Metadata" or "SSH Keys"
- You might be able to add your key there

---

## METHOD 3: Recreate Instance with New Key (If Nothing Works)

If you really can't find where to add the key, you can:

**Step 1:** Create a new Compute Instance
- Click **Compute** → **Instances**
- Click **Create Instance**
- When it asks for SSH key, paste your new public key there
- Launch the instance

**Step 2:** Use the setup script:
```bash
bash /tmp/setup-oracle-cloud.sh
```

---

## ALTERNATIVELY: Use Your Original Key

Do you remember which key you used when you **first created** the Oracle instance?

That might be easier! Try this command with the **minecraft.ppk** file:

```powershell
# First, check if PuTTY is installed
"C:\Program Files\PuTTY\puttygen.exe" --help

# If it is, convert the key
"C:\Program Files\PuTTY\puttygen.exe" "C:\Users\Ronald mcdonald\Documents\key\minecraft.ppk" -O private-openssh-new -o -c "" -o "C:\Users\Ronald mcdonald\.ssh\minecraft_key"

# Then try SSH with the converted key
ssh -i "C:\Users\Ronald mcdonald\.ssh\minecraft_key" ubuntu@150.136.13.134
```

---

## QUICK TEST: Try Direct SSH Access

Once you've added the key, test it with:

```powershell
ssh -i "$HOME\.ssh\oracle_key" ubuntu@150.136.13.134
```

If you see:
- `ubuntu@instance-name:~$` = SUCCESS! ✅
- `Permission denied` = Key not added yet
- `Connection refused` = Firewall issue

---

## Need Help Finding SSH Keys Section?

**Common locations in Oracle Cloud Console:**

1. **Compute Instance Details Page** (most common)
   - Path: Compute → Instances → [Your Instance Name]
   - Look: Bottom section, "SSH Keys" or "Metadata"

2. **Instance Edit Page**
   - Path: Same page, click three dots (⋯) → Edit
   - Look: Scroll to bottom for "SSH Keys"

3. **Network Security Details**
   - Path: Compute → Instances → [Instance Name] → Links/Resources
   - Look: "Primary VNIC" → "Security Lists"

4. **Oracle Linux vs Ubuntu**
   - If Ubuntu: SSH keys might be under "Cloud Init" section
   - If Oracle Linux: Different menu structure

---

## TELL ME:

1. **Can you see the instance details page?**
   - If yes, what sections do you see? (describe the fields/buttons)

2. **What's the exact name of your instance?**

3. **Does your instance status show "RUNNING"?**

4. **Try this first:** When on the instance details page, scroll all the way to the bottom - do you see any section with "SSH" or "Key" or "Public"?

