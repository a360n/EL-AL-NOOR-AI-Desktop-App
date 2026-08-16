#!/bin/bash
# ======================================================================
#   EL AL-NOOR AI ☀️🤖 - Solar Panels Quality Inspection Platform
#   معمل النور للألواح الشمسية - تشغيل التطبيق المكتبي على نظام macOS
# ======================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "======================================================================"
echo "  EL AL-NOOR AI ☀️🤖 - تشغيل المنظومة الذكية لفحص الألواح الشمسية"
echo "  معمل النور للألواح الشمسية - macOS Application Launcher"
echo "======================================================================"
echo ""

# Check python3
if ! command -v python3 &> /dev/null
then
    echo "❌ [ERROR] Python 3 is not installed or not in PATH!"
    echo "يرجى تثبيت بايثون 3 من الموقع الرسمي: https://www.python.org/downloads/"
    read -p "اضغط Enter للإغلاق..."
    exit 1
fi

echo "🚀 جاري تشغيل المنظومة وفحص التحديثات..."
python3 "$DIR/main.py"

read -p "اضغط Enter للإغلاق..."
