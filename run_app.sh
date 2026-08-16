#!/usr/bin/env bash
echo "======================================================================"
echo "   EL AL-NOOR AI - Solar Panels Quality Inspection Platform"
echo "   معمل النور للألواح الشمسية - تشغيل التطبيق المكتبي"
echo "======================================================================"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
python3 "$DIR/main.py"
