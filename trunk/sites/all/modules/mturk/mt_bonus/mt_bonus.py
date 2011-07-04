from mt_task import MTTaskApp
from org.drupal.project.async_command import Result
import sys

class MTBonusApp(MTTaskApp):

  #Override
  def identifier(self):
    return 'mt_bonus'

  def grant_bonus(self, bonus_id):
    row = self.query('SELECT worker_id, bonus_amount, assignment_id, message FROM {mt_bonus} WHERE bonus_id=?', bonus_id)[0]
    worker_id, bonus_amount, assignment_id, message = row['worker_id'], row['bonus_amount'], row['assignment_id'], row['message']
    bonus_amount = bonus_amount.doubleValue()  # original is BigDecimal.
    #self.service.grantBonus(worker_id, bonus_amount, assignment_id, message)
    return Result(True, 'Granted bonus: ' + str(bonus_amount) + ' to ' + worker_id)


if __name__ == '__main__':
  app = MTBonusApp()
  app.handleCLI(sys.argv)
