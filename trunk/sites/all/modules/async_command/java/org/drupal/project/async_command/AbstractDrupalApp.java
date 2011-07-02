package org.drupal.project.async_command;

import bsh.EvalError;
import bsh.Interpreter;
import org.apache.commons.cli.*;
import org.apache.commons.codec.binary.Base64;
import org.apache.commons.dbcp.BasicDataSourceFactory;
import org.apache.commons.dbutils.QueryRunner;
import org.apache.commons.dbutils.handlers.MapListHandler;
import org.apache.commons.dbutils.handlers.ScalarHandler;
import org.lorecraft.phparser.SerializedPhpParser;

import javax.sql.DataSource;
import java.io.*;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.SQLException;
import java.text.MessageFormat;
import java.util.*;
import java.util.logging.Logger;

/**
 * all external program/script should extends this class for easier access.
 * If using SQL queries, please follow SQL-92 standard to allow maximum compatibility.
 */
abstract public class AbstractDrupalApp {

    protected DataSource dataSource;
    protected Logger logger = Logger.getLogger(this.getClass().getName());

    protected RunningMode runningMode = RunningMode.ONCE;
    protected Properties config = new Properties();

    String configFilePath = getDefaultConfigFilePath();
    String dbPrefix;
    int maxBatchSize;

    /**
     * @return The name of the drupal application.
     */
    abstract public String identifier();

    public enum RunningMode {
        ONCE,
        CONTINUOUS,
        LISTENING
    }

    public enum EncryptionMethod {
        NONE,
        BASE64,
        MCRYPT
    }

    /**
     * run the Drupal application using the default settings
     */
    public void runApp() {
        // first, try to establish drupal database connection
        initDrupalConnection();

        // prepare to run App.
        prepareApp();

        // retrieve a list of command.
        List<Map<String, Object>> commandList = null;
        try {
            commandList = query("SELECT id, command, uid, eid, created FROM {async_command} " +
                    "WHERE app=? AND status IS NULL ORDER BY created", identifier());
        } catch (SQLException e) {
            logger.severe("Cannot query async_command table.");
            throw new DrupalRuntimeException(e);
        }

        // TODO: also print out a list of command.
        logger.info("Total commands to be executed: " + commandList.size());
        for (Map<String, Object> commandRecord : commandList) {
            int id = ((Long)(commandRecord.get("id"))).intValue();
            String command = (String)(commandRecord.get("command"));

            logger.info("Running async_command: " + command);
            Result result = null;
            try {
                // prepare the command
                prepareCommand((Integer)commandRecord.get("uid"), (Integer)commandRecord.get("eid"), (Integer)commandRecord.get("created"));
                // execute the command
                result = runCommand(command);
            } catch (EvaluationFailureException e) {
                updateRecord(id, false, "Command evaluation error. See script log for details. Error: " + e.getMessage());
                e.printStackTrace();
                continue;
            } catch (DrupalRuntimeException e) {
                updateRecord(id, false, e.getMessage());
                e.printStackTrace();
                continue;
            }
            updateRecord(id, result.getStatus(), result.getMessage());
            //logger.info("Result: " + result.getStatus() + " " + result.getMessage().substring(0, 100));
            logger.info("Result: " + result.getStatus());
        }
    }

    /**
     * Subclass can choose to run some code in order to prepare for the DrupalApp.
     */
    protected void prepareApp() {
        // do nothing in default settings.
    }

    /**
     * Run the async command. Derived classes should handle exceptions.
     */
    protected Result runCommand(String command) throws EvaluationFailureException {
        try {
            // run each command
            Interpreter interpreter = new Interpreter();
            interpreter.set("app", this);
            Result result = (Result) interpreter.eval("app."+ command);
            return result;
        } catch (EvalError e) {
            logger.severe("Cannot execute the command: " + command);
            throw new EvaluationFailureException(e);
        } catch (ClassCastException e) {
            logger.severe("The command should return a Result object.");
            throw new EvaluationFailureException(e);
        }
    }


    protected void prepareCommand(int uid, int eid, int created) {
        // do nothing in default settings.
        // subclass could do some preparation for the command based on uid and eid.
    }


    void updateRecord(int id, boolean status, String message) {
        long changed = new Date().getTime() / 1000;
        try {
            update("UPDATE {async_command} SET status=?, message=?, changed=? WHERE id=?", status, message, changed, id);
        } catch (SQLException e) {
            logger.severe("Cannot update status in async_command.");
            throw new DrupalRuntimeException(e);
        }
    }

    /**
     * establish database connection to Drupal database. set dataSource property abd other parameters.
     */
    void initDrupalConnection() {
        assert dataSource == null;  // assert that it hasn't been initialized yet.
        try {
            File configFile = new File(configFilePath);
            if (!configFile.exists()) {
                throw new DrupalRuntimeException("Database configuration file "+ configFilePath +" doesn't exists.");
            }

            // read configuration file.
            Reader configReader = new FileReader(configFile);
            config.load(configReader);

            // set Drupal db prefix
            if (config.containsKey("prefix")) {
                String p = config.getProperty("prefix").trim();
                if (p.length() != 0) {
                    dbPrefix = p;
                }
            }

            maxBatchSize = config.containsKey("db_max_batch_size") ? Integer.parseInt(config.getProperty("db_max_batch_size")) : 0;
            if (maxBatchSize > 0) {
                logger.info("Batch SQL size: " + maxBatchSize);
            }

            // create data source.
            dataSource = BasicDataSourceFactory.createDataSource(config);

        } catch (IOException e) {
            logger.severe("Error reading configuration file.");
            throw new DrupalRuntimeException(e);
        } catch (Exception e) {
            logger.severe("Error initializing DataSource for Drupal database connection.");
            throw new DrupalRuntimeException(e);
        }
        // test connection
    }

    public void testConnection() {
        initDrupalConnection();
        try {
            //QueryRunner q = new QueryRunner(dataSource);
            //List<Map<String, Object>> rows = q.query(d("SELECT * FROM {async_command} WHERE app=?"), new MapListHandler(), identifier());
            //for (Map<String, Object> row : rows) {
            //    System.out.println(row.get("id") + ":" + row.get("command"));
            //}
            // TODO-postponed: should use more sophisticated test on user privileges.
            Connection conn = dataSource.getConnection();
            DatabaseMetaData metaData = conn.getMetaData();
            logger.info("Database connection successful: " + metaData.getDatabaseProductName() + metaData.getDatabaseProductVersion());
            //ResultSet rs = metaData.getColumnPrivileges(null, null, d("{async_command}"), "id");
        } catch (SQLException e) {
            logger.severe("SQL error during testing connection.");
            throw new DrupalRuntimeException(e);
        }
    }

    private String getDefaultConfigFilePath() {
        String workingDir = System.getProperty("user.dir");
        return workingDir + File.separator + "config.properties";
    }

    /**
     * "decorate" the SQL statement for Drupal. replace {table} with prefix.
     * @param sql the original SQL statement to be decorated.
     * @return the "decorated" SQL statement
     */
    protected String d(String sql) {
        String newSql;
        if (dbPrefix != null) {
            newSql = sql.replaceAll("\\{(.+?)\\}", dbPrefix+"_"+"$1");
        }
        else {
            newSql = sql.replaceAll("\\{(.+?)\\}", "$1");
        }
        //logger.info(newSql);
        return newSql;
    }

    /**
     * Simply run Drupal database queries without using d(). e.g., query("SELECT nid, title FROM {node} WHERE type=?", "forum");
     * @param sql the SQL query to be executed, do not use d()
     * @param params parameters to complete the SQL query
     * @return a list of rows as Map
     * @throws SQLException
     */
    protected List<Map<String, Object>> query(String sql, Object... params) throws SQLException {
        QueryRunner q = new QueryRunner(dataSource);
        List<Map<String, Object>> result = q.query(d(sql), new MapListHandler(), params);
        return result;
    }

    /**
     * Simply run Drupal database queries without using d(); returning 1 value.
     * e.g., query("SELECT title FROM {node} WHERE nid=?", 1);
     * @param sql the SQL query to be executed, do not use d()
     * @param params parameters to complete the SQL query
     * @return one value object
     * @throws SQLException
     */
    protected Object queryValue(String sql, Object... params) throws SQLException {
        QueryRunner q = new QueryRunner(dataSource);
        Object result = q.query(d(sql), new ScalarHandler(), params);
        return result;
    }

    /**
     * Simply run Drupal database queries without using d(). e.g., query("UPDATE {node} SET sticky=1 WHERE type=?", "forum");
     * @param sql the SQL query to be executed, do not use d()
     * @param params parameters to complete the SQL query
     * @return number of rows affected
     * @throws SQLException
     */
    protected int update(String sql, Object... params) throws SQLException {
        QueryRunner q = new QueryRunner(dataSource);
        int num = q.update(d(sql), params);
        return num;
    }


    protected int[] batch(String sql, Object[][] params) throws SQLException {
        Connection connection = dataSource.getConnection();
        connection.setAutoCommit(false);
        int[] num = batch(connection, sql, params);
        connection.commit();
        connection.close();
        return num;
    }

    protected int[] batch(Connection connection, String sql, Object[][] params) throws SQLException {
        QueryRunner q = new QueryRunner(dataSource);
        String processedSql = d(sql);
        // fix slow problem [#1185100]
        if (maxBatchSize > 0) {
            int start = 0;
            int end = 0;
            int count;
            int[] num = new int[params.length];
            do {
                end += maxBatchSize;
                if (end > params.length) {
                    end = params.length;
                }
                int[] batchNum =  q.batch(connection, processedSql, Arrays.copyOfRange(params, start, end));
                for (count=0; count<batchNum.length; count++) {
                    num[start+count] = batchNum[count];
                }
                start = end;
            } while (end < params.length);
            return num;
        } else {
            return q.batch(connection, processedSql, params);
        }
    }

    /**
     * this function handles CLI; users of the class should call this function.
     * @param args arguments from main()
     */
    public void handleCLI(String[] args) {
        // build command parser
        Options options = buildOptions();
        CommandLineParser parser = new PosixParser();
        CommandLine command = null;
        try {
            command = parser.parse(options, args);
        } catch (ParseException exp) {
            logger.severe("Cannot parse parameters. Please use -h to see help. Error message: " + exp.getMessage());
            return;
        }

        // get configurable settings. non-exclusive.
        handleCommandSettings(command);

        // handle executable options, mutual exclusive
        handleCommandExecutables(command);
    }


    private void handleCommandExecutables(CommandLine command) {
        // mutual exclusive options.
        if (command.hasOption('h')) {
            // print help message and exit.
            HelpFormatter formatter = new HelpFormatter();
            formatter.printHelp("Drupal application -- " + identifier(), buildOptions());
        }
        else if (command.hasOption('t')) {
            // test connection and exit.
            testConnection();
        }
        else if (command.hasOption('e')) {
            // run command directly and exit.
            initDrupalConnection();
            prepareApp();
            String evalStr = command.getOptionValue('e');
            try {
                Result result = runCommand(evalStr);
                String successMsg = result.getStatus() ? "succeeds" : "fails";
                logger.info("Running " + successMsg + ". Message: " + result.getMessage());
            } catch (EvaluationFailureException e) {
                logger.severe("Cannot evaluate script from command line.");
                throw new DrupalRuntimeException(e);
            }
        }
        else {
            // run the application command by command. could be time-consuming
            runApp();
        }
    }


    private void handleCommandSettings(CommandLine command) {
        if (command.hasOption('c')) {
            configFilePath = command.getOptionValue('c');
            logger.info("Set configuration file as: " + configFilePath);
        }
        if (command.hasOption('r')) {
            String rm = command.getOptionValue('r');
            if (rm.equals("once")) {
                runningMode = RunningMode.ONCE;
            } else if (rm.equals("continuous")) {
                // TODO: not supported yet
                throw new UnsupportedOperationException();
                //runningMode = RunningMode.CONTINUOUS;
            } else if (rm.equals("listening")) {
                // TODO: not supported yet
                throw new UnsupportedOperationException();
                //runningMode = RunningMode.LISTENING;
            } else {
                logger.severe("Cannot parse parameters for -r. Please use -h to see help. Use default running mode.");
            }
        }
    }


    /**
     * If subclass needs to set properties, Use config.properties instead of override the method here.
     */
    private Options buildOptions() {
        Options options = new Options();
        options.addOption("c", true, "database configuration file");
        options.addOption("r", true, "program running mode: 'once' (default), 'continuous', or 'listening'");
        options.addOption("h", "help", false, "print this message");
        options.addOption("t", "test", false, "test connection to Drupal database");
        options.addOption("e", "eval", true, "evaluate a method call directly");
        return options;
    }

    /**
     * This is the same as handleCLI()
     * @param args
     */
    public void run(String[] args) {
        handleCLI(args);
    }

    /**
     * Function to help read encrypted settings field from "encset" module.
     */
    protected Properties readEncryptedSettingsField(String value, EncryptionMethod encryptionMethod) {
        String origValue = null;
        switch (encryptionMethod) {
            case NONE:
                origValue = value;
                break;
            case BASE64:
                origValue = new String(Base64.decodeBase64(value));
                break;
            case MCRYPT:
                if (!config.containsKey("mcrypt_secret_key")) {
                    throw new DrupalRuntimeException("Need mcrypt_secret_key in the config file in order to decrypt.");
                }
                String secretKey = config.getProperty("mcrypt_secret_key");
                origValue = evalPhp("echo rtrim(mcrypt_decrypt(MCRYPT_3DES,''{0}'',base64_decode(''{1}''),''ecb''),''\\0'');", secretKey, value);
                origValue = origValue.trim();
                break;
        }

        Properties properties = new Properties();
        try {
            properties.load(new StringReader(origValue));
        } catch (IOException e) {
            logger.severe("Cannot read encrypted settings field.");
            throw new DrupalRuntimeException(e);
        }
        return properties;
    }

    protected Properties readEncryptedSettingsField(String value) {
        return readEncryptedSettingsField(value, EncryptionMethod.MCRYPT);
    }


    /**
     * Be very careful of using single quote in pattern. Needs to use two single quotes for PHP string.
     * @see java.text.MessageFormat
     */
    protected String evalPhp(String pattern, Object... params) {
        assert (pattern!=null && !pattern.isEmpty());
        // generate PHP code following java.text.MessageFormat.format()
        String phpCode = MessageFormat.format(pattern, params);
        //System.out.println(phpCode);
        return evalPhp(phpCode);
    }

    protected String evalPhp(String phpCode) {
        // retrieve php cli executable
        // TODO: test with 'php -v' before executing the command.
        String phpCli = config.getProperty("php_cli", "php");
        String[] cmd = {phpCli,  "-r", phpCode};

        try {
            // run the command
            Process process = Runtime.getRuntime().exec(cmd);
            process.waitFor();
            if (process.exitValue() != 0) {
                logger.severe("PHP process exception.");
                throw new DrupalRuntimeException("Unexpected PHP error: " + process.exitValue());
            }
            // read output
            StringBuilder sb = new StringBuilder();
            int c;
            Reader input = new InputStreamReader(process.getInputStream());
            while ((c = input.read()) != -1) {
                sb.append((char)c);
            }
            return sb.toString();
        } catch (IOException e) {
            logger.severe("Cannot run PHP code. Possible reasons: missing PHP CLI executable or dependent libraries.");
            throw new DrupalRuntimeException(e);
        } catch (InterruptedException e) {
            logger.severe("PHP code interrupted.");
            throw new DrupalRuntimeException(e);
        }
    }

    protected Map<String, Object> unserializePhpArray(String serialized) {
        SerializedPhpParser serializedPhpParser = new SerializedPhpParser(serialized);
 		return (Map<String, Object>) serializedPhpParser.parse();
    }

    /**
     * Convert the byte[] blog value from this.queryValue() to a string. Might not work for all cases.
     * @param blobValue a byte[] array
     * @return a string
     */
    protected String convertBlobValueToString(Object blobValue) {
        //assert blobValue.getClass().isInstance((byte[]).getClass());
        byte[] blobBytes = (byte[]) blobValue;
        return new String(blobBytes);
    }

    /**
     * Make sure varName exists.
     * @param varName the Drupal variable name
     * @return the value of the variable, could be float, integer, string, or PhpObject as PHP array.
     * @see SerializedPhpParser
     */
    protected Object drupalVariableGet(String varName) {
        try {
            Object serializedBytes = queryValue("SELECT value FROM {variable} WHERE name=?", varName);
            String serialized = convertBlobValueToString(serializedBytes);
            SerializedPhpParser serializedPhpParser = new SerializedPhpParser(serialized);
 		    return serializedPhpParser.parse();
        } catch (SQLException e) {
            throw new DrupalRuntimeException(e);
        } catch (ClassCastException e) {
            throw new DrupalRuntimeException(e);
        }
    }

    /**
     * Set Drupal variable. Doesn't guarantee to work. Use with Caution.
     * @param varName the variable name.
     * @param varValue the variable value in PHP code string.
     */
    protected void drupalVariableSet(String varName, String varValue) {
        String serialized = evalPhp("echo serialize(''{0}'');", varValue);
        byte[] serializedBytes = serialized.getBytes();
        try {
            update("UPDATE {variable} SET value=? WHERE name=?", serializedBytes, varName);
        } catch (SQLException e) {
            throw new DrupalRuntimeException(e);
        }
    }

    /**
     * @see http://code.google.com/p/json-simple/wiki/EncodingExamples
     * @see http://code.google.com/p/json-simple/
     * @param obj The object to be encoded
     */
    /*protected String encodeJSON(Object obj) {
        return JSONValue.toJSONString(obj);
    }*/


    /**
     * @see http://code.google.com/p/json-simple/wiki/DecodingExamples
     * @see http://code.google.com/p/json-simple/
     * @param jsonText json text to be decoded.
     * @return the JSON object, caller should change it to Map of List or other primitives.
     */
    /*protected Object decodeJSON(String jsonText) {
        return JSONValue.parse(jsonText);
    }*/

}
