package org.leohelper.android;

import android.app.job.JobParameters;
import android.app.job.JobService;

public final class UpdateJobService extends JobService {
    private volatile JobParameters runningJob;

    @Override public boolean onStartJob(JobParameters params) {
        runningJob = params;
        new Thread(() -> {
            ReleaseUpdates.Release release = null;
            boolean retry = false;
            try {
                release = ReleaseUpdates.latest(this);
            } catch (Exception networkFailure) {
                retry = true;
            }
            if (runningJob == params) {
                ReleaseUpdates.notifyOnce(this, release);
                jobFinished(params, retry);
                runningJob = null;
            }
        }, "leo-update-job").start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters params) {
        if (runningJob == params) runningJob = null;
        return true;
    }
}
