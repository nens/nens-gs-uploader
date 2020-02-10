if not defined in_subprocess (cmd /k set in_subprocess=y ^& %0 %*) & exit )
echo off
call "%~dp0install_environment.bat"
call C:\Users\%username%\AppData\Local\Continuum\anaconda3\Scripts\activate.bat 
echo activate catalogue
call activate catalogue
REM echo install install gsconfig
REM call pip install gsconfig-py3==1.0.7
echo Finished installing catalogue environment
cd /D "%~dp0"
