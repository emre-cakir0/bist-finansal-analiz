@echo off
REM BIST Finansal Analiz uygulamasini baslatir (proje klasorunden cift tiklayin)
cd /d "%~dp0.."
python -m streamlit run app\app.py
