pipeline {
  agent { label 'windows' }

  options {
    timestamps()
  }

  parameters {
    string(
      name: 'WORKSPACE_DIR',
      defaultValue: '',
      description: 'Absolute path to the project folder'
    )
  }

  environment {
    PYTHONUNBUFFERED = '1'
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
    PIP_CACHE_DIR = "${WORKSPACE}\\.pip-cache"
  }

  stages {

    stage('Resolve project directory') {
      steps {
        script {
          if (!params.WORKSPACE_DIR?.trim()) {
            error "WORKSPACE_DIR parameter must be provided"
          }
          env.EFFECTIVE_DIR = params.WORKSPACE_DIR.trim()
        }
        bat '''
          echo Using project dir: %EFFECTIVE_DIR%
          dir "%EFFECTIVE_DIR%"
        '''
      }
    }

    stage('Show Environment') {
      steps {
        dir("${env.EFFECTIVE_DIR}") {
          bat '''
            echo WORKSPACE=%WORKSPACE%
            echo PROJECT_DIR=%EFFECTIVE_DIR%
            python --version
            pip --version
          '''
        }
      }
    }

    stage('Create venv + Install deps') {
      steps {
        dir("${env.EFFECTIVE_DIR}") {
          bat '''
            if exist .venv rmdir /s /q .venv
            python -m venv .venv

            call .venv\\Scripts\\activate.bat
            python -m pip install --upgrade pip

            pip install -r requirements.txt
          '''
        }
      }
    }

    stage('Lint (ruff)') {
      steps {
        dir("${env.EFFECTIVE_DIR}") {
          bat '''
            call .venv\\Scripts\\activate.bat
            set PYTHONPATH=%EFFECTIVE_DIR%

            ruff check .
          '''
        }
      }
    }

    stage('Unit Tests') {
      steps {
        dir("${env.EFFECTIVE_DIR}") {
          bat '''
            call .venv\\Scripts\\activate.bat
            set PYTHONPATH=%EFFECTIVE_DIR%

            if not exist test-results mkdir test-results

            pytest -q --disable-warnings --maxfail=1 ^
              --junitxml=test-results\\junit.xml
          '''
        }
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: '**/test-results/junit.xml'
        }
      }
    }

    stage('Coverage (optional)') {
      steps {
        dir("${env.EFFECTIVE_DIR}") {
          bat '''
            call .venv\\Scripts\\activate.bat
            set PYTHONPATH=%EFFECTIVE_DIR%

            pytest -q ^
              --cov=src --cov-report=term-missing ^
              --cov-report=xml:coverage.xml ^
              --cov-report=html:htmlcov
          '''
        }
      }
      post {
        always {
          archiveArtifacts artifacts: '**/coverage.xml, **/htmlcov/**', allowEmptyArchive: true
        }
      }
    }
  }

  post {
    always {
      bat 'echo Done.'
    }
  }
}
