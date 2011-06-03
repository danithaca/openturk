OPENTURK_HOME=/home/mrzhou/openturk
ASYNC_COMMAND_HOME=$OPENTURK_HOME/sites/all/modules/async_command
MT_ANALYSIS_HOME=$OPENTURK_HOME/sites/all/modules/mt_analysis
MT_TASK_HOME=$OPENTURK_HOME/sites/all/modules/mt_task
MTURK_SDK_HOME=/opt/java-aws-mturk-1.2.2
JYTHON_HOME=/opt/jython-2.5.2rc4
CONFIG_FILE=$OPENTURK_HOME/sites/default/config.properties


export CLASSPATH="${CLASSPATH}:$(find "$ASYNC_COMMAND_HOME/lib" -name "*.jar" | tr '\n' ':')"
export CLASSPATH="${CLASSPATH}:$(find "$MTURK_SDK_HOME/lib" -name "*.jar" | tr '\n' ':')"
export PYTHONPATH=$PATHONPATH:$MT_ANALYSIS_HOME

$JYTHON_HOME/jython $MT_TASK_HOME/script.py -c $CONFIG_FILE
$JYTHON_HOME/jython $MT_ANALYSIS_HOME/script.py -c $CONFIG_FILE
