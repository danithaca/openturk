ASYNC_COMMAND_HOME=../sites/all/modules/async_command
MTURK_SDK_HOME=/opt/java-aws-mturk-1.2.2
JYTHON_HOME=/opt/jython-2.5.2rc4
CONFIG_FILE=../sites/default/config.properties

export CLASSPATH="${CLASSPATH}:$(find "$ASYNC_COMMAND_HOME/lib" -name "*.jar" | tr '\n' ':')"
export CLASSPATH="${CLASSPATH}:$(find "$MTURK_SDK_HOME/lib" -name "*.jar" | tr '\n' ':')"

$JYTHON_HOME/jython ../sites/all/modules/mt_task/script.py -c $CONFIG_FILE
