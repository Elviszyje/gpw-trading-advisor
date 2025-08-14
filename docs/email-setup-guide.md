# Email Configuration Guide

## Overview
Your GPW Trading Advisor notification system is ready to send both **Telegram** and **Email** notifications. The Telegram part is already working perfectly. To enable email notifications, you need to configure an SMTP email server.

## Quick Setup Options

### Option 1: Gmail (Recommended for Testing) 🚀

**Steps:**
1. Use your Gmail account or create a new one specifically for the app
2. Enable 2-Factor Authentication on your Gmail account
3. Generate an "App Password" (not your regular Gmail password):
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a new app password for "Mail"
4. Update your `.env` file with these settings:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_16_character_app_password
DEFAULT_FROM_EMAIL=GPW Trading Advisor <your_email@gmail.com>
```

### Option 2: Outlook/Hotmail

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-mail.outlook.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@outlook.com
EMAIL_HOST_PASSWORD=your_password
DEFAULT_FROM_EMAIL=GPW Trading Advisor <your_email@outlook.com>
```

### Option 3: Custom Domain/Business Email

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.yourdomain.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=notifications@yourdomain.com
EMAIL_HOST_PASSWORD=your_password
DEFAULT_FROM_EMAIL=GPW Trading Advisor <notifications@yourdomain.com>
```

### Option 4: Keep Console Mode (Testing Only)

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

## Testing Email Setup

After configuring your email settings, test them:

```bash
# Test email notifications
python manage.py process_enhanced_notifications --test-email your_test_email@gmail.com

# Test both email and Telegram
python manage.py process_enhanced_notifications --test-email your_test_email@gmail.com
python manage.py process_enhanced_notifications --test-telegram 7676229144
```

## Security Best Practices

### For Gmail:
- ✅ Use App Passwords (never your main Gmail password)
- ✅ Enable 2-Factor Authentication
- ✅ Consider creating a dedicated Gmail account for the app

### For Business Email:
- ✅ Use a dedicated email account like `notifications@yourdomain.com`
- ✅ Ensure SMTP access is enabled
- ✅ Use strong passwords

### Environment Security:
- ✅ Never commit `.env` file to version control
- ✅ Keep email credentials secure
- ✅ Rotate passwords regularly

## Current Notification Features ✅

### Working Now:
- **Telegram Notifications**: ✅ Fully operational
- **Email Infrastructure**: ✅ Ready (needs SMTP config)
- **Template System**: ✅ Professional HTML/text emails
- **Async Processing**: ✅ High performance
- **Multi-channel Delivery**: ✅ Email + Telegram simultaneously

### Notification Types Ready:
1. **Trading Signal Alerts** - Real-time buy/sell signals
2. **Daily Trading Summaries** - Market overview and performance
3. **Price Alerts** - Custom price threshold notifications
4. **System Notifications** - Status updates and alerts

## Example Email Templates

Your system includes professional email templates:

### Signal Alert Email:
- **Subject**: "🎯 Trading Signal: PKO - BUY"
- **Content**: Stock details, confidence level, target/stop prices
- **Format**: HTML with text fallback

### Daily Summary Email:
- **Subject**: "📊 Daily Trading Summary - 2025-01-23"
- **Content**: Market statistics, top signals, performance metrics
- **Format**: Professional HTML layout

## Next Steps

1. **Choose your email provider** (Gmail recommended for testing)
2. **Update `.env` file** with your email settings
3. **Test the configuration** using the management commands
4. **Verify email delivery** in your inbox
5. **Enjoy automated notifications!** 🎉

## Troubleshooting

### Common Issues:

**Authentication Failed:**
- Check username/password
- For Gmail: Use App Password, not regular password
- Verify 2FA is enabled for Gmail

**Connection Refused:**
- Check EMAIL_HOST and EMAIL_PORT
- Verify firewall/network settings
- Ensure SMTP is enabled on your email provider

**Emails Not Received:**
- Check spam/junk folders
- Verify recipient email address
- Test with different email addresses

### Debug Mode:
To see detailed email sending logs, check the Django console output when running the test commands.

---

**Your notification system is now ready for production use!** 🚀
