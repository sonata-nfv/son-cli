set -e

if [ "$#" -ne 4 ]; then
	echo "Usage: `basename "$0"` <REPO_NAME> <COMPONENT> <DISTRIBUTION> <DEB_PACKAGE_DIR>"
	exit 1
fi

APTLY_REPO_NAME=$1
APTLY_COMPONENT=$2
APTLY_DISTRIBUTION=$3
DEB_PACKAGE_DIR=$4

aptly repo create \
    -component="$APTLY_COMPONENT" \
    -distribution="$APTLY_DISTRIBUTION" \
    $APTLY_REPO_NAME

for old in ./$DEB_PACKAGE_DIR/*.deb; do new=$(echo $old | sed -e 's/\.deb$/_'$APTLY_DISTRIBUTION'.deb/'); mv -v "$old" "$new"; done

aptly repo add $APTLY_REPO_NAME $DEB_PACKAGE_DIR

aptly repo show $APTLY_REPO_NAME

if [ ! -z "$GPG_PASSPHRASE" ]
then
    passphrase="$GPG_PASSPHRASE"
elif [ ! -z "$GPG_PASSPHRASE_FILE" ]
then
    passphrase=$(<$GPG_PASSPHRASE_FILE)
fi

aptly publish repo \
    -architectures="$APTLY_ARCHITECTURES" \
    -passphrase="$passphrase" \
    $APTLY_REPO_NAME

if [ ! -z "$KEYSERVER" ] && [ ! -z "$URI" ]
then
    release_sig_path=$(find ~/.aptly/public/dists -name Release.gpg | head -1)
    gpg_key_id=$(gpg --list-packets $release_sig_path | grep -oP "(?<=keyid ).+")

    echo "# setup script for $URI for repository $APTLY_REPO_NAME" >> ~/.aptly/public/go

    case "$URI" in
        https://*)
            cat >> ~/.aptly/public/go <<-END
if [ ! -e /usr/lib/apt/methods/https ]
then
    apt-get update
    apt-get install -y apt-transport-https
fi
END
    esac

    cat >> ~/.aptly/public/go <<-END
apt-key adv --keyserver $KEYSERVER --recv-keys $gpg_key_id
echo "deb $URI $APTLY_DISTRIBUTION $APTLY_COMPONENT" >> /etc/apt/sources.list
apt-get update
END
fi

#tar -C /repo -czf /debs/repo.tar.gz .