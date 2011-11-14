OPENTURK_HOME=/home/mrzhou/openturk
ASYNC_COMMAND_HOME=$OPENTURK_HOME/sites/all/modules/async_command
MTURK_MODULE_HOME=$OPENTURK_HOME/sites/all/modules/mturk
MTURK_SDK_HOME=/opt/java-aws-mturk-1.2.2
JYTHON_HOME=/opt/jython-2.5.2
CONFIG_FILE=$OPENTURK_HOME/sites/default/config.properties


export CLASSPATH="$(find "$ASYNC_COMMAND_HOME/lib" -name "*.jar" | tr '\n' ':')"
export CLASSPATH="${CLASSPATH}:$(find "$MTURK_SDK_HOME/lib" -name "*.jar" | tr '\n' ':')"
export CLASSPATH=$ASYNC_COMMAND_HOME/drupal-app.jar:$CLASSPATH
#export PYTHONPATH=$PYTHONPATH:$MTURK_MODULE_HOME/mt_task:$MTURK_MODULE_HOME/mt_analysis
PYTHONPATH=$PYTHONPATH:$MTURK_MODULE_HOME/mt_task:$MTURK_MODULE_HOME/mt_analysis:$MTURK_MODULE_HOME/mt_bonus:$MTURK_MODULE_HOME/mt_karma
export JYTHONPATH=$PYTHONPATH

#$JYTHON_HOME/jython $MTURK_MODULE_HOME/mt_task/mt_task.py -c $CONFIG_FILE
#$JYTHON_HOME/jython $MTURK_MODULE_HOME/mt_analysis/mt_analysis.py -c $CONFIG_FILE
#$JYTHON_HOME/jython $MTURK_MODULE_HOME/mt_bonus/mt_bonus.py -c $CONFIG_FILE
$JYTHON_HOME/jython -Dpython.security.respectJavaAccessibility=false $MTURK_MODULE_HOME/mturk.py
