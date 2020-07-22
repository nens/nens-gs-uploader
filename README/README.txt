atlas2catlogue.py wordt gebruikt om een catalogus op te bouwen uit een bestaande atlas.
De volgende stappen worden binnen deze scripts gevolgd:
	1. vectors, rasters en andere externe wmslagen worden opgehaald uit een atlas.	
	2. Vectors worden gecheckt op boundingbox en geometrie. Valt de vector buiten het atlas gebied? Dan dient deze opnieuw geupload te worden ().
	4. Valt de vector binnen de bbox, dan wordt er een wmslayer aangemaakt met de (meta)data uit de atlas.	
	5. Rasters worden altijd geclipt en opnieuw geupload met (meta)data uit de atlas.
	6. Een summary (met errors) wordt gegenereerd. Hierin kan je zien wat er fout is gegaan en naar welke lagen nog gekeken moeten worden. 


Stappen om atlas2catalogue.py te gebruiken.
	1. Kloon https://github.com/nens/nens-gs-uploader naar je computer.
	2. Download anaconda: https://www.anaconda.com/products/individual.
	3. Mocht je anaconda al hebben doe eerst: conda update conda.
	3. Installeer de juiste omgeving. 
		- Draai daarvoor op nens-gs-uploader/install/install_environment.bat vanuit je anaconda command prompt.
		- werkt dit niet? Draai dan de commands uit create_env.txt in dezelfde folder in anaconda command prompt.
	4. Open de juiste omgeving: Type [conda activate catalogue]  in je anaconda prompt.
	5. Vul nens-gs-uploader/catalogue/instellingen/atlas2catalogue.ini met de juiste instellingen. Zet bij [tool] alles op False behalve wd en epsg voor de standaard procedure.
	   Je moet ook een dataset aanmaken --> Dit wordt niet voor je gedaan.
	6. Draai vervolgens atlas2catalogue.py met het ini bestandje nens-gs-uploader/catalogue/instellingen/atlas2catalogue.ini
	7. Na afloop van het script wordt een overzicht gegenereerd. De meeste fouten komen voor doordat je vector buiten het gebied valt of je rasters niet te vinden zijn in Lizard.

Controleer altijd alle lagen in de catalogus! Met name de beschrijvingen moeten worden gecontroleerd worden ivm het format van beschrijvingen in de atlas.
