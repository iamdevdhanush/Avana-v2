from git_filter_repo import RepoFilter

def commit_callback(commit, metadata):
    if commit.author_email == b"=itsdevdhanush":
        commit.author_name = b"iamdevdhanush"
        commit.author_email = b"dhanushdprabhu18@gmail.com"

    if commit.committer_email == b"=itsdevdhanush":
        commit.committer_name = b"iamdevdhanush"
        commit.committer_email = b"dhanushdprabhu18@gmail.com"

RepoFilter(
    commit_callback=commit_callback
).run()