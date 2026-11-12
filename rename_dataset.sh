#!/usr/bin/env bash
# Chay trong thu muc EduHub (Git Bash):  bash rename_dataset.sh
# Doi ten tep: bo dau cach, sua loi chinh ta Sile -> Slide, thong nhat dau gach duoi.
set -e
cd dataset
mv -n "K1/Physics/Classical Mechanics_Gravity.mp4"       "K1/Physics/Classical_Mechanics_Gravity.mp4"
mv -n "K1/Physics/Classical Mechanics_Gravity_img.png"   "K1/Physics/Classical_Mechanics_Gravity_img.png"
mv -n "K1/Physics/Classical Mechanics_ProblemSet.pdf"    "K1/Physics/Classical_Mechanics_ProblemSet.pdf"
mv -n "K2/KNTU/Sile_Bai_Giang.pptx"                      "K2/KNTU/Slide_Bai_Giang.pptx"
mv -n "K2/KNTU/Sile_Bai_Giang.zip"                       "K2/KNTU/Slide_Bai_Giang.zip"
mv -n "K2/KNTU/Sile_Bai_Giang-KNTU.pdf"                  "K2/KNTU/Slide_Bai_Giang_KNTU.pdf"
echo "Da doi ten. Ten hien tai:"; find . -type f | sort
