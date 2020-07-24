if not defined in_subprocess (cmd /k set in_subprocess=y ^& %0 %*) & exit )
echo installing catalogue environment
call conda config --add channels conda-forge
call conda create -n catalogue python=3.6.9 configparser=3.7.4 gdal=2.4.1 tqdm=4.40.2 json5=0.8.5  beautifulsoup4=4.8.1 psycopg2=2.8.4 requests owslib rtree python-slugify
echo Finished installing catalogue environment
pause