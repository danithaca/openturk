'''
Currently, we only use the read-only operations in mturk SDK. For 'write' operations, we provide this script. You can write your own script extends it.
You can use the default '-e' option to directly run some commands without using commands saved in the database.
Make sure you have the mt_task sub-directory in PYTHONPATH
'''
from ConfigParser import ConfigParser
from mt_task import MTTaskApp


DEFAULT_UID = 0
DEFAULT_EID = 0
DEFAULT_DB_CONF = 'mysql.conf'


class MTUtilsStandalone(MTTaskApp):

  #Override
  def identifier(self):
    return 'mt_utils'

  def __init__(self):
    self.init(DEFAULT_UID, DEFAULT_EID)

  def get_db_conn(config_file=DEFAULT_DB_CONF):
    config = ConfigParser.ConfigParser()
    config.read(config_file)
    db = "jdbc:mysql://" + config.get('client', 'host') + '/' + config.get('client', 'database')
    user = config.get('client', 'user')
    passwd = config.get('client', 'password')
    driver = "org.gjt.mm.mysql.Driver"
    #print (db, user, passwd, driver)
    conn = zxJDBC.connect(db, user, passwd, driver)
    cursor = conn.cursor()
    return conn, cursor


  ##########################################################

  def message_qual(self, qual_id, subject, message):
    workers = []
    qrs = self.service.getAllQualificationRequests(qual_id)
    for i in range(len(qrs)):
      q = qrs[i]
      workers.append(q.getSubjectId())
    self._notify_workers(subject, message, workers)


  def _notify_workers(self, subject, message, workers, batch_size = 100):
    print "Total recipients:", len(workers)
    batches = (len(workers)-1)/batch_size + 1
    for batch in range(batches):
      rp = workers[batch*batch_size : (batch+1)*batch_size]
      print "Sending messages to", len(rp), "recipients"
      self.service.notifyWorkers(subject, message, rp)