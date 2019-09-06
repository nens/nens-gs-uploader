CREATE TABLE metadata (
    id          	SERIAL PRIMARY KEY,
    pg_layer        varchar(255),
    gs_workspace 	varchar(255),
	gs_store        varchar(255),
    gs_layer	    varchar(255),
    uploader        varchar(255),
    projectnummer   varchar(255),
    einddatum       varchar(255)
  
	
  );