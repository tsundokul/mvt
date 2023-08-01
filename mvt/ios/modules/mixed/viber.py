import logging
import os
import sqlite3
from typing import Optional

from mvt.common.utils import check_for_links, convert_mactime_to_iso

from ..base import IOSExtraction

"""
A Manifest.db fileID is generated using the following algorithm
    > sha1(domain + '-' + relative_filename)
    eg.
    sha1(AppDomainGroup-group.viber.share.container-com.viber/database/Contacts.data)
        = 83b9310399a905c7781f95580174f321cd18fd97
"""
VIBER_APP_DOMAIN = "AppDomainGroup-group.viber.share.container"
VIBER_BACKUP_PATHS = [
    "private/var/mobile/Containers/Shared/AppGroup/*/com.viber/database/Contacts.data",
    "private/var/mobile/Applications/*/com.viber/database/Contacts.data",
]
VIBER_BACKUP_IDS = ["83b9310399a905c7781f95580174f321cd18fd97"]


class Viber(IOSExtraction):
    """This modul extracts all URLs from a Viber sqlite database"""

    def __init__(
        self,
        file_path: Optional[str] = None,
        target_path: Optional[str] = None,
        results_path: Optional[str] = None,
        module_options: Optional[dict] = None,
        log: logging.Logger = logging.getLogger(__name__),
        results: Optional[list] = None,
    ) -> None:
        super().__init__(
            file_path=file_path,
            target_path=target_path,
            results_path=results_path,
            module_options=module_options,
            log=log,
            results=results,
        )

    def serialize(self, record: dict) -> dict:
        text = record["message"].replace("\n", "\\n")
        user = record.get("fullname", "<unknown>")
        phone_number = record.get("phone_number", "<unknown number>")
        links = "- Embedded links: " + ", ".join(record["links"])

        return {
            "timestamp": record["isodate"],
            "module": self.__class__.__name__,
            "event": "entry_modified",
            "data": f"{text} from user {user} ({phone_number}) {links}",
        }

    def check_indicators(self) -> None:
        if not self.indicators:
            return

        for result in self.results:
            ioc = self.indicators.check_domains(result["links"])
            if ioc:
                result["matched_indicator"] = ioc
                self.detected.append(result)

    def run(self) -> None:
        backup_paths = set()

        if self.is_backup:
            # Locate matching backup files by 'domain' field in Manifest.db (iTunes backup)
            for backup_file in self._get_backup_files_from_manifest(
                domain=VIBER_APP_DOMAIN
            ):
                if backup_file["file_id"] in VIBER_BACKUP_IDS:
                    backup_path = self._get_backup_file_from_id(backup_file["file_id"])

                    if backup_path:
                        backup_paths.add(backup_path)

        elif self.is_fs_dump:
            for log_path in self._get_fs_files_from_patterns(VIBER_BACKUP_PATHS):
                self.log.info("Found Viber log at path: %s", log_path)
                key = os.path.relpath(log_path, self.target_path)
                backup_paths.add(key)

        for backup in backup_paths:
            self.log.info("Processing Viber database at %s", backup)
            self._process_backup_db(backup)

        self.log.info(
            "Extracted %d messages with links from Viber backups", len(self.results)
        )

    def _process_backup_db(self, backup_path: str) -> None:
        """This method reads a viber SQLite database and extracts all URLs from messages"""
        self._recover_sqlite_db_if_needed(backup_path)

        # sqlite also has context managers for connections and cursors
        conn = sqlite3.connect(backup_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                ZVIBERMESSAGE.ZTEXT,
                ZVIBERMESSAGE.ZDATE,
                ZPHONENUMBER.ZPHONE,
                ZMEMBER.ZDISPLAYFULLNAME
            FROM
                ZVIBERMESSAGE, Z_5PHONENUMINDEXES, ZMEMBER, ZPHONENUMBER
            WHERE
                ZVIBERMESSAGE.ZCONVERSATION = Z_5PHONENUMINDEXES.Z_5CONVERSATIONS
            AND
                Z_5PHONENUMINDEXES.Z_10PHONENUMINDEXES = ZPHONENUMBER.Z_PK
            AND
                ZPHONENUMBER.ZMEMBER = ZMEMBER.Z_PK
        """
        )

        # Fetching a few rows at a time makes it more memory efficient
        # when there are many rows returned
        FETCHLIMIT = 100
        rows = cur.fetchmany(FETCHLIMIT)

        while rows:
            for row in rows:
                # row[1] is the column containing the text message
                links = check_for_links(row[0])
                if not links:
                    continue

                self.results.append(
                    {
                        "message": row[0],
                        "isodate": convert_mactime_to_iso(row[1]),
                        "phone_number": row[2],
                        "fullname": row[3],
                        "links": links,
                    }
                )
            rows = cur.fetchmany(FETCHLIMIT)

        cur.close()
        conn.close()
