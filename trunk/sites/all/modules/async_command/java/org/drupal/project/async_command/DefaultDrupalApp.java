package org.drupal.project.async_command;

public class DefaultDrupalApp extends AbstractDrupalApp {
    @Override
    public String identifier() {
        return "default";
    }

    public Result dummy() {
        return dummy(null);
    }

    public Result dummy(String message) {
        if (message == null) {
            return new Result(true, "no message");
        } else if (message.equals("fail me")) {
            return new Result(false, "mission failed.");
        } else {
            String msg = "You said " + message;
            return new Result(true, msg);
        }
    }

    public static void main(String[] args) {
        DefaultDrupalApp app = new DefaultDrupalApp();
        app.handleCLI(args);
    }

}
