package org.drupal.project.async_command;

public class EvaluationFailureException extends Exception {
    public EvaluationFailureException(Throwable e) {
        super(e);
    }
}
