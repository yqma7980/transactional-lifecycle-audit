# Third-party source and redistribution scope

The numerical comparisons are author-derived records. No complete third-party
package, Python runtime, binary wheel, issue-comment collection or user-profile
collection is redistributed in this addition. Native adapters/fixtures are
author-created study code. Small source references visible in error traces are
attributed to their exact upstream package/version. Original Django and Celery
license notices are retained under `upstream_notices`.

Source identities are provided rather than claiming blanket confidentiality:

- Django: https://github.com/django/django ; before/after commits and Python 3.8.20
  dependency versions are recorded in `environment/r079_ENVIRONMENT.json`.
- Celery: https://github.com/celery/celery ; before/after commits and Python 3.12.10
  dependency versions are recorded in `environment/r094_ENVIRONMENT.json`.
- Click #412: https://github.com/pallets/click/issues/412 ; fix
  `851ce7fc58d5ee57e3910a12094d3df986bb0ff8`, first parent
  `7f1d70c54565ec978f49dc78a65299f9e94cd01d`. Source-qualified, contract binding held.
- Trio #55: https://github.com/python-trio/trio/issues/55 ; no authoritative
  fix/first-parent pair admitted under the fixed historical screening protocol.

Dependency names/versions are factual metadata, not licenses to redistribute
those packages. Obtain dependencies from their upstream sources under the
applicable licenses. This archive does not claim endorsement by any upstream
project. Third-party rights are not overwritten by the author-data license.
