# دليل إعداد البوت على خادم VPS

هذا الدليل يشرح كيفية تثبيت وإعداد بوت التداول الآلي على خادم VPS بعد نقله من Replit.

## متطلبات النظام

### الحد الأدنى من المواصفات
- نظام تشغيل: Ubuntu 20.04 أو أحدث
- ذاكرة RAM: 1 جيجابايت كحد أدنى
- مساحة تخزين: 10 جيجابايت كحد أدنى
- اتصال إنترنت مستقر

### البرمجيات المطلوبة
- Python 3.9 أو أحدث
- pip (مدير حزم Python)
- Git

## خطوات الإعداد

### 1. تثبيت البرمجيات الأساسية

```bash
# تحديث النظام
sudo apt update
sudo apt upgrade -y

# تثبيت Python وأدوات التطوير
sudo apt install -y python3 python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools python3-venv git

# التحقق من إصدار Python
python3 --version
```

### 2. إعداد البيئة الافتراضية

```bash
# إنشاء مجلد للمشروع
mkdir -p ~/crypto-bot
cd ~/crypto-bot

# استنساخ المستودع من GitHub
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git .

# إنشاء بيئة افتراضية
python3 -m venv venv

# تفعيل البيئة الافتراضية
source venv/bin/activate

# تثبيت المتطلبات
pip install -r dependencies.txt
```

### 3. إعداد المتغيرات البيئية

```bash
# إنشاء ملف .env
cp .env-example .env

# تحرير ملف .env لإضافة بيانات الاعتماد الخاصة بك
nano .env
```

أضف مفاتيح API الخاصة بك إلى ملف `.env`:

```
MEXC_API_KEY=your_api_key_here
MEXC_API_SECRET=your_api_secret_here
TELEGRAM_BOT_TOKEN=your_telegram_token_here (اختياري)
TELEGRAM_CHAT_ID=your_telegram_chat_id_here (اختياري)
```

### 4. تشغيل البوت

```bash
# تشغيل البوت مباشرة
python main.py
```

## تشغيل البوت في الخلفية

### باستخدام screen
```bash
# تثبيت screen
sudo apt install -y screen

# إنشاء جلسة screen جديدة
screen -S crypto-bot

# تفعيل البيئة الافتراضية
source venv/bin/activate

# تشغيل البوت
python main.py

# فصل الجلسة (اضغط Ctrl+A ثم D)
```

للعودة إلى الجلسة لاحقًا:
```bash
screen -r crypto-bot
```

### باستخدام systemd (للتشغيل التلقائي عند إعادة تشغيل الخادم)

1. إنشاء ملف خدمة systemd:

```bash
sudo nano /etc/systemd/system/crypto-bot.service
```

2. أضف المحتوى التالي:

```
[Unit]
Description=Crypto Trading Bot
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/crypto-bot
ExecStart=/home/YOUR_USERNAME/crypto-bot/venv/bin/python /home/YOUR_USERNAME/crypto-bot/main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=crypto-bot

[Install]
WantedBy=multi-user.target
```

استبدل `YOUR_USERNAME` باسم المستخدم الخاص بك.

3. تفعيل وتشغيل الخدمة:

```bash
sudo systemctl enable crypto-bot.service
sudo systemctl start crypto-bot.service
```

4. التحقق من حالة الخدمة:

```bash
sudo systemctl status crypto-bot.service
```

## مراقبة السجلات

```bash
# مشاهدة سجلات systemd (إذا كنت تستخدم systemd)
sudo journalctl -u crypto-bot.service -f

# أو يمكنك إضافة سجل إلى ملف محدد عن طريق تعديل main.py
```

## النسخ الاحتياطي

قم بإنشاء مهمة cron لعمل نسخ احتياطي منتظم لملف الصفقات:

```bash
# فتح محرر crontab
crontab -e

# إضافة سطر لعمل نسخة احتياطية كل ساعة
0 * * * * cp /home/YOUR_USERNAME/crypto-bot/active_trades.json /home/YOUR_USERNAME/crypto-bot/backups/active_trades_$(date +\%Y\%m\%d\%H\%M\%S).json
```

## ملاحظات هامة

1. **وقت النظام**: تأكد من أن وقت النظام مزامن بشكل صحيح، وهو أمر مهم للتداول.
   ```bash
   sudo apt install -y ntp
   ```

2. **حماية الخادم**: قم بتكوين جدار الحماية وتحديث النظام بانتظام.
   ```bash
   sudo apt install -y ufw
   sudo ufw allow ssh
   sudo ufw allow 5000  # لواجهة الويب
   sudo ufw enable
   ```

3. **مراقبة الأداء**: قم بتثبيت أدوات مراقبة مثل htop لمراقبة أداء النظام.
   ```bash
   sudo apt install -y htop
   ```