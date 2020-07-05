if not defined in_subprocess (cmd /k set in_subprocess=y ^& %0 %*) & exit )
echo off
call "%~dp0install_environment.bat"
echo activate catalogue
call activate catalogue
echo Finished installing catalogue environment
cd /D "%~dp0"
