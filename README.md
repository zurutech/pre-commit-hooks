# Pre Commit Hooks

This repository is used to store all zuru scripts that are run in our CI pipelines during the pre-commit job. If you want them in your repo, you'll have to:

- Allow your project under the CI_JOB_TOKEN Access Token settings
- Add the pre-commit CI template in the .gitlab-ci.yml file of your repository

## Using pre-commit-hooks with pre-commit

All projects that have to use these pre-commit scripts need to be in the allow list of this repository (Settings > CI/CD > Token Access and write the repository location).
In the .gitlab-ci.yml of your project you'll need to reference the CI Template we're using for the pre-commit by adding this:

```yaml
include:
  - project: zuru.tech/operations/ci-templates                             
    file: .pre-commit.yml   
    ref: main
```

The template is located [here](https://gitlab.com/zuru.tech/operations/ci-templates/-/blob/main/.pre-commit.yml?ref_type=heads), all the fiels can be overwritten in the pre-commit job of your CI in case you need to do something differently. 

WARNING: if the job gets the forbidden response when downloading the template, make sure that the PRE_COMMIT_TOKEN CI/CD variables is set under the group Zuru Home in gitlab. The token needs the priviledges to read the CI Templates repository.

The job will use the .pre-commit-config.yaml located in the root directoy of your repository. An example of how to use a hook:

```yaml
  - repo: https://gitlab.com/zuru.tech/operations/pre-commit-hooks
    rev: latest
    hooks:
      - id: copyright_updater
```

The `rev` field indicates the tag or the release of the code of this repository. At the moment the `rev` will always have to be `latest` and only the code in the latest commit of the main branch will be used. Since there is no latest tag there will be a warning in the pre-commit job.

## Add pre-commit hooks scripts to this repo

If you need to add your script you'll have to:

- Add the script in the pre_commit_hooks folder
- Define the entrypoint in the setup.cfg in the `\[options.entry_points\]` section
- Define the prehook and its arguments in the .pre-commit-hooks.yaml file. All options are visible [here](https://pre-commit.com/#new-hooks)
