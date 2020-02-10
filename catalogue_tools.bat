if not defined in_subprocess (cmd /k set in_subprocess=y ^& %0 %*) & exit )
echo off
call C:\Users\%username%\AppData\Local\Continuum\anaconda3\Scripts\activate.bat 
echo activate catalogue
call activate catalogue
cd /D "%~dp0"
