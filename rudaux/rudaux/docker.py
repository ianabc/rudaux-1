import docker
import time

class DockerError(Exception):
    def __init__(self, message, docker_output):
        self.message = message
        self.docker_output = docker_output

class Docker(object):

    def __init__(self, config, dry_run):
        self.client = docker.from_env()
        self.image = config.grading_image
        self.dry_run = dry_run
        self.n_threads = config.num_docker_threads
        self.mem_per_thread = config.docker_memory
        self.jobs = {}
        self.job_id = 0
        self.runsts = ['running', 'created']

    def submit(self, command, homedir = None):
        key = 'job-' + str(self.job_id)
        self.jobs[key] = {'command': command, 'homedir' : homedir}
        self.job_id += 1
        return key

    def run(self, command, homedir = None):
        ctr, result = self._run_container(command, homedir)
        if ctr:
            while ctr.status in self.runsts:
                time.sleep(0.25)
                ctr.reload()
            result['exit_status'] = ctr.status
            result['log'] = ctr.logs(stdout = True, stderr = True).decode('utf-8')
            ctr.remove(force = True)
        return result

    def run_all(self):
        print('Docker running ' + str(len(self.jobs)) + ' jobs')
        results = {}
        running = {}
        print_every = 30
        job_keys = [key for key in self.jobs]
        while len(running) > 0 or len(job_keys) > 0:

            # sleep while we have reached max threads and all running
            time_since_print = 0
            while len(running) >= self.n_threads and all([running[k].status in self.runsts for k in running]):
                time.sleep(0.25)
                time_since_print += 0.25
                for k in running:
                    running[k].reload()
                if time_since_print >= print_every:
                    print('Jobs still running: ' + str(list(running.keys())))
                    time_since_print = 0

            # refresh the status of all running containers (we may have not made it into the above loop)
            for k in running:
                running[k].reload()

            # clean out nonrunning containers
            to_pop = []
            for k in running:
                if running[k].status not in self.runsts:
                    results[k]['exit_status'] = running[k].status
                    results[k]['log'] = running[k].logs(stdout = True, stderr = True).decode('utf-8')
                    running[k].remove(force = True)
                    to_pop.append(k)
            for k in to_pop:
                running.pop(k, None)

            # add a new container if there are any remaining
            time.sleep(0.25) #sleep for a 1/4 second for stability when starting containers...?
            if len(job_keys) > 0:
                assert len(running) < self.n_threads
                key = job_keys.pop()
                print('Running ' + str(key) +': ' + self.jobs[key]['command'] + ' in ' + self.jobs[key]['homedir'])
                results[key] = {}
                ctr, results[key] = self._run_container(self.jobs[key]['command'], self.jobs[key]['homedir'])
                if ctr:
                    running[key] = ctr

        # clear the commands queue when done
        self.jobs = {} 

        return results

    def _run_container(self, command, homedir):
        ctr = None
        result = {}
        #TODO don't do this here, but maybe in the external caller: email instructor when errors?
        try:
            if not self.dry_run:
                ctr = self.client.containers.run(self.image, command,
                                                      detach = True,
                                                      remove = False,
                                                      stderr = True,
                                                      stdout = True,
                                                      mem_limit = self.mem_per_thread,
                                                      volumes = {homedir : {'bind': '/home/jupyter', 'mode': 'rw'}} if homedir else {}
                                                      )
            else:
                print('[Dry Run: would have started docker container with command: ' + command + ']')
                result['exit_status'] = 'dry_run'
                result['log'] = 'dry_run'
        except docker.errors.APIError as e:
            print('Docker APIError exception encountered when starting docker container')
            print('Command: ' + command)
            print('Homedir: ' + homedir)
            result['exit_status'] = 'never_started'
            result['log'] = 'ERROR: Docker APIError, ' + str(e)
            ctr = None
        except docker.errors.ImageNotFound as e:
            print('Docker ImageNotFound exception encountered when starting docker container')
            print('Command: ' + command)
            print('Homedir: ' + homedir)
            result['exit_status'] = 'never_started'
            result['log'] = 'ERROR: Docker ImageNotFound, ' + str(e)
            ctr = None
        except Exception as e:
            print('Unknown exception encountered when starting docker container')
            print('Command: ' + command)
            print('Homedir: ' + homedir)
            result['exit_status'] = 'never_started'
            result['log'] = 'ERROR: Unknown exception, ' + str(e) 
            ctr = None
        return ctr, result



