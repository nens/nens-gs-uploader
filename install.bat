call C:\Users\%username%\AppData\Local\Continuum\anaconda3\Scripts\activate.bat 
echo installing catalogue environment
conda create -n catalogue python=3.6.9 configparser=3.7.4 gdal=2.4.1 tqdm=4.40.2 json5=0.8.5  beautifulsoup4=4.8.1 psycopg2=2.8.4
activate
pip install gsconfig-py=1.0.7
echo Finished installing catalogue environment
pause

