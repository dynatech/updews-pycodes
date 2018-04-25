import dynadb.db as dbio
import volatile.memory as mem
import volatile.static as static
from datetime import datetime as dt
import time
import MySQLdb

def check_number_in_table(num):
    """
        **Description:**
          - Checks if the cellphone number exists in users or loggers table.
         
        :param num: number of the recipient.
        :type num: int
        :returns: table name **users** or **loggers** (*int*)
    """
    query = ("Select  IF((select count(*) FROM user_mobile where sim_num ='%s')>0,'1','0')" 
    "as user,IF((select count(*) FROM logger_mobile where sim_num ='%s')>0,'1','0') as logger limit 80"%(num,num))
    query_check_number = db.read(query,'check number in table')

    if query_check_number[0][0] > query_check_number[0][1]:
        return 'users'
    elif query_check_number[0][0] < query_check_number[0][1]:
        return 'loggers'
    elif query_check_number[0][0] == '0' and query_check_number[0][1] == '0':
        return False


def set_read_status(sms_id_list, read_status=0, table='', host='local'):
    
    if table == '':
        print "Error: Empty table"
        return

    if type(sms_id_list) is list:
        if len(sms_id_list) == 0:
            return
        else:
            where_clause = ("where inbox_id "
                "in (%s)") % (str(sms_id_list)[1:-1].replace("L",""))
    elif type(sms_id_list) is long:
        where_clause = "where inbox_id = %d" % (sms_id_list)
    else:
        print ">> Unknown type"        
    query = "update smsinbox_%s set read_status = %d %s" % (table, read_status, 
        where_clause)
    
    # print query
    dbio.write(query, "set_read_status", False, host)

def set_send_status(table, status_list, host):
    # print status_list
    query = ("insert into smsoutbox_%s_status (stat_id,send_status,ts_sent,outbox_id,gsm_id,mobile_id) "
        "values ") % (table[:-1])

    for stat_id,send_status,ts_sent,outbox_id,gsm_id,mobile_id in status_list:
        query += "(%d,%d,'%s',%d,%d,%d)," % (stat_id,send_status,ts_sent,outbox_id,gsm_id,mobile_id)

    query = query[:-1]
    query += (" on duplicate key update stat_id=values(stat_id), "
        "send_status=send_status+values(send_status),ts_sent=values(ts_sent)")

    # print query
    
    dbio.write(query, "set_send_status", False, host)

def get_inbox(host='local', read_status=0, table='loggers', limit=200):
    db, cur = dbio.connect(host)

    if table in ['loggers','users']:
        tbl_contacts = '%s_mobile' % table[:-1]
    else:
        print 'Error: unknown table', table
        return
    
    while True:
        try:
            query = ("select inbox_id,ts_sms,sim_num,sms_msg from "
                "(select inbox_id,ts_sms,mobile_id,sms_msg from smsinbox_%s "
                "where read_status = %d order by inbox_id desc limit %d) as t1 "
                "inner join (select mobile_id, sim_num from %s) as t2 "
                "on t1.mobile_id = t2.mobile_id ") % (table, read_status, limit,
                tbl_contacts)
            # print query
        
            a = cur.execute(query)
            out = []
            if a:
                out = cur.fetchall()
            return out

        except MySQLdb.OperationalError:
            print '9.',
            time.sleep(20)

def get_all_outbox_sms_from_db(table='users',send_status=5,gsm_id=5,limit=10):
    """
        **Description:**
          -The function that get all outbox message that are not yet send.
         
        :param table: Table name and **Default** to **users** table .
        :param send_status:  **Default** to **5**.
        :param gsm_id: **Default** to **5**.
        :param limit: **Default** to **10**.
        :type table: str
        :type send_status: str
        :type gsm_id: int
        :type limit: int
        :returns: List of message
    """
    sc = mem.server_config()
    host = sc['resource']['smsdb']

    while True:
        try:
            db, cur = dbio.connect(host)
            query = ("select t1.stat_id,t1.mobile_id,t1.gsm_id,t1.outbox_id,t2.sms_msg from "
                "smsoutbox_%s_status as t1 "
                "inner join (select * from smsoutbox_%s) as t2 "
                "on t1.outbox_id = t2.outbox_id "
                "where t1.send_status < %d "
                "and t1.send_status >= 0 "
                "and t1.gsm_id = %d "
                "limit %d ") % (table[:-1],table,send_status,gsm_id,limit)
          
            a = cur.execute(query)
            out = []
            if a:
                out = cur.fetchall()
                db.close()
            return out

        except MySQLdb.OperationalError:
            print '10.',
            time.sleep(20)

def write_inbox(msglist,gsm_info):
    """
        **Description:**
          -The write raw sms to database function that write raw  message in database.
         
        :param msglist: The message list.
        :param gsm_info: The gsm_info that being use.
        :type msglist: obj
        :type gsm_info: obj
        :returns: N/A
    """
    sc = mem.server_config()
    mobile_nums_db = sc["resource"]["mobile_nums_db"]

    logger_mobile_sim_nums = static.get_mobiles('loggers', mobile_nums_db)
    user_mobile_sim_nums = static.get_mobiles('users', mobile_nums_db)

    # gsm_ids = get_gsm_modules()

    ts_stored = dt.today().strftime("%Y-%m-%d %H:%M:%S")

    gsm_id = gsm_info['id']

    loggers_count = 0
    users_count = 0

    query_loggers = ("insert into smsinbox_loggers (ts_sms, ts_stored, mobile_id, "
        "sms_msg,read_status,gsm_id) values ")
    query_users = ("insert into smsinbox_users (ts_sms, ts_stored, mobile_id, "
        "sms_msg,read_status,gsm_id) values ")

    sms_id_ok = []
    sms_id_unk = []
    ts_sms = 0
    ltr_mobile_id= 0

    for m in msglist:
        # print m.simnum, m.data, m.dt, m.num
        ts_sms = m.dt
        sms_msg = m.data
        read_status = 0 
    
        if m.simnum in logger_mobile_sim_nums.keys():
            query_loggers += "('%s','%s',%d,'%s',%d,%d)," % (ts_sms, ts_stored,
                logger_mobile_sim_nums[m.simnum], sms_msg, read_status, gsm_id)
            ltr_mobile_id= logger_mobile_sim_nums[m.simnum]
            loggers_count += 1
        elif m.simnum in user_mobile_sim_nums.keys():
            query_users += "('%s','%s',%d,'%s',%d,%d)," % (ts_sms, ts_stored,
                user_mobile_sim_nums[m.simnum], sms_msg, read_status, gsm_id)
            users_count += 1
        else:            
            print 'Unknown number', m.simnum
            sms_id_unk.append(m.num)
            continue

        sms_id_ok.append(m.num)

    query_loggers = query_loggers[:-1]
    query_users = query_users[:-1]

    sc = mem.server_config()
    sms_instance = sc["resource"]["smsdb"]

    if len(sms_id_ok)>0:
        if loggers_count > 0:
            dbio.write(query_loggers,'write_raw_sms_to_db',
                instance = sms_instance)
        if users_count > 0:
            dbio.write(query_users,'write_raw_sms_to_db',
                instance = sms_instance)
        
def write_outbox(message='',recipients='',gsm_id='',table=''):
    """
        **Description:**
          -The write outbox message to database is a function that insert message to smsoutbox with 
          timestamp written,message source and mobile id.
         
        :param message: The message that will be sent to the recipients.
        :param recipients: The number of the recipients.
        :param gsm_id: The gsm id .
        :param table: table use of the number.
        :type message: str
        :type recipients: str
        :type recipients: int
        :type table: str
        :returns: N/A
    """
    # if table == '':
    #     print "Error: No table indicated"
    #     raise ValueError
    #     return

    sc = mem.server_config()

    host = sc['resource']['smsdb']

    tsw = dt.today().strftime("%Y-%m-%d %H:%M:%S")

    if table == '':
        table_name = check_number_in_table(recipients[0])
    else:
        table_name = table

    query = ("insert into smsoutbox_%s (ts_written,sms_msg,source) VALUES "
        "('%s','%s','central')") % (table_name,tsw,message)
        
    outbox_id = dbio.write(query = query, identifier = "womtdb", 
        last_insert = True, instance = host)[0][0]

    query = ("INSERT INTO smsoutbox_%s_status (outbox_id,mobile_id,gsm_id)"
            " VALUES ") % (table_name[:-1])

    table_mobile = static.get_mobiles(table_name, host)

    for r in recipients.split(","):        
        tsw = dt.today().strftime("%Y-%m-%d %H:%M:%S")
        try:
            print outbox_id, table_mobile[r], gsm_id
            query += "(%d,%d,%d)," % (outbox_id,table_mobile[r],gsm_id)
        except KeyError:
            print ">> Error: Possible key error for", r
            continue
    query = query[:-1]

    dbio.write(query = query, identifier = "womtdb", 
        last_insert = False, instance = host)