"""Offline contracts for the real clean-room runner. Never start Docker here."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.p072_clean_room import CleanRoom, Failure, gate_result, docs_only, volume_script


class CleanRoomTests(unittest.TestCase):
    def test_existing_state_is_refused_without_running_a_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'.local').mkdir()
            runner=CleanRoom(root,'a'*40)
            with patch.object(runner,'command') as command:
                with self.assertRaises(Failure):runner.check_fresh()
                command.assert_not_called()

    def test_unknown_dependencies_and_symlink_state_are_refused(self):
        for name in ('client/node_modules','client/dist','.local'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.symlink_to(root/'missing')
                with self.assertRaises(Failure):CleanRoom(root,'a'*40).check_fresh()

    def test_public_failure_report_excludes_private_output_and_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner=CleanRoom(Path(temporary),'a'*40)
            secret='synthetic-private-cookie-value'
            with self.assertRaises(Failure):
                runner.stage('browser',lambda:(_ for _ in ()).throw(Failure(17,secret)))
            report=runner.public_report()
            self.assertEqual(report['stages'][0]['exit_code'],17)
            self.assertEqual(report['stages'][0]['name'],'browser')
            self.assertNotIn(secret,str(report))
            self.assertFalse(report['accepted'])

    def test_volume_restore_rejects_links_and_escaping_paths(self):
        # Actual safe extraction runs in the isolated volume helper in real CI.
        script=volume_script('restore','config')
        self.assertIn('member.issym()',script)
        self.assertIn("'..' in parts",script)
        self.assertIn('member.islnk()',script)
        with self.assertRaises(ValueError):volume_script('restore','../../outside')

    def test_volume_roundtrip_is_independent_and_rejects_malicious_archives(self):
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source';source.mkdir();backup=root/'backup';backup.mkdir();restored=root/'restored';restored.mkdir()
            (source/'proof').write_bytes(b'fixed synthetic bytes')
            def execute(action,path):
                exec(volume_script(action,'config').replace("'/volume'",repr(str(path))).replace("'/backup/config.tar'",repr(str(backup/'config.tar'))),{})
            execute('backup',source);(source/'proof').write_bytes(b'changed source')
            execute('restore',restored)
            self.assertEqual((restored/'proof').read_bytes(),b'fixed synthetic bytes')
            self.assertFalse((restored/'proof').samefile(source/'proof'))
            for name,kind in (('data/../../escape',tarfile.REGTYPE),('data/link',tarfile.SYMTYPE)):
                with tarfile.open(backup/'config.tar','w') as archive:
                    entry=tarfile.TarInfo(name);entry.type=kind;entry.linkname='/outside';archive.addfile(entry,io.BytesIO())
                with self.assertRaises(ValueError):execute('restore',restored)

    def test_git_scope_checks_both_sides_of_code_to_document_rename(self):
        import subprocess
        from scripts.p0_ci_policy import changed_paths
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            def git(*args):return subprocess.check_output(['git','-C',str(root),'-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',*args],stderr=subprocess.DEVNULL,text=True).strip()
            git('init');git('config','user.name','Synthetic');git('config','user.email','test@example.invalid')
            (root/'src').mkdir();(root/'src/code.py').write_text('synthetic')
            git('add','.');git('commit','-m','before');base=git('rev-parse','HEAD')
            (root/'docs').mkdir();(root/'src/code.py').rename(root/'docs/code.md')
            git('add','-A');git('commit','-m','after');head=git('rev-parse','HEAD')
            paths=changed_paths(base,head,root)
            self.assertEqual(set(paths),{'src/code.py','docs/code.md'});self.assertFalse(docs_only(paths))
            self.assertIsNone(changed_paths('0'*40,head,root))

    def test_docs_only_has_explicit_allowlist_and_empty_is_not_exempt(self):
        self.assertTrue(docs_only(['ROADMAP.md','docs/LOCAL_WORKSPACE.md','artifact/proof.png']))
        for paths in ([],['docs/run.py'],['roadmap/_checks.json'],['.github/workflows/real-matrix.yml'],['src/gitdocs.py'],['README.md','client/src/App.jsx']):
            self.assertFalse(docs_only(paths),paths)

    def test_real_gate_never_accepts_failed_skipped_or_unclassified_code(self):
        self.assertEqual(gate_result('success','false','success','success'),'real')
        self.assertEqual(gate_result('success','true','skipped','skipped'),'docs-only-exemption')
        for args in (('failure','true','skipped','skipped'),('success','false','success','failure'),('success','false','skipped','skipped'),('success','oops','success','success'),('success','true','failure','skipped')):
            with self.subTest(args=args),self.assertRaises(Failure):gate_result(*args)


if __name__=='__main__':unittest.main()
