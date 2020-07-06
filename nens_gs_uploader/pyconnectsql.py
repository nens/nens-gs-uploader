# -*- coding: utf-8 -*-
"""#
Created on Mon Dec 17 14:15:26 2018

@author: chris.kerklaan - N&S

README
De klasse connect2pg maakt een connectie naar je postgis database
Ook kun je hier een sql file runnen.

Connectie kan op verschillende manieren:
1. psycopg
2. ogr

Credits voor dit script gaan naar de rastercaster:
https://github.com/nens/threedi-turtle-scripts/blob/master/sql-scripts/rastercaster/rastercaster.py

"""
# third-party imports
import ogr
import psycopg2


class connect2pg:
    def __init__(
        self, dbname, port="5432", host="localhost", user="postgres", password="nens",
    ):
        self.dbname = dbname
        self.host = host
        self.user = user
        self.password = password
        self.port = port

    def psycopg2_connection(self):
        db_conn = ("dbname={} user={} host={} password={}").format(
            self.dbname, self.user, self.host, self.password
        )
        try:
            conn = psycopg2.connect(db_conn)
        except:
            print("I am unable to connect to the database")

        return conn

    def ogr_connection(self, connection="string", read=1):
        ogr_conn = ("PG:host={} port={} user='{}'" "password='{}' dbname='{}'").format(
            self.host, self.port, self.user, self.password, self.dbname
        )

        if connection is True:
            try:
                ogr_conn = ogr.Open(ogr_conn, read)
            except:
                print("I am unable to connect to the database")
                print(ogr_conn)
        elif connection is "string":
            pass
        else:
            print("connection paramater not properly selected")

        return ogr_conn

    def execute_sql_file(self, filename, *args):
        print("Started execute_sql_file:" + filename)

        conn = self.psycopg2_connection()
        cur = conn.cursor()

        with open(filename, "r") as file:
            sql = file.read()

            if len(args) > 0:
                for num, arg in enumerate(args):
                    sql = sql.replace("arg{}".format(str(num)), str(arg))

        #            if args is not None:
        #                f = file.read()
        #                for num,i in enumerate(arg):
        #                    f = f.replace('arg{}'.format(str(num)),str(i))
        #                sql = f
        #            else:
        #                sql = file.read()

        print(sql)
        cur.execute(sql)
        conn.commit()

        # except psycopg2.DatabaseError as e:

        if conn:
            conn.rollback()
            conn.close()

        conn.close()

        # finally:
        if conn is not None:
            conn.close()

    def execute_sql(self, sql):
        conn = self.psycopg2_connection()
        cur = conn.cursor()

        cur.execute(sql)
        conn.commit()

        if conn:
            conn.rollback()
            conn.close()

        conn.close()

        # finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    pass
