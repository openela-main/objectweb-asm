%bcond_without junit5
%bcond_without osgi

Name:           objectweb-asm
Version:        7.3.1
Release:        3%{?dist}
Summary:        Java bytecode manipulation and analysis framework
License:        BSD
URL:            http://asm.ow2.org/
BuildArch:      noarch

# ./generate-tarball.sh
Source0:        %{name}-%{version}.tar.gz
Source1:        parent.pom
Source2:        https://repo1.maven.org/maven2/org/ow2/asm/asm/%{version}/asm-%{version}.pom
Source3:        https://repo1.maven.org/maven2/org/ow2/asm/asm-analysis/%{version}/asm-analysis-%{version}.pom
Source4:        https://repo1.maven.org/maven2/org/ow2/asm/asm-commons/%{version}/asm-commons-%{version}.pom
Source5:        https://repo1.maven.org/maven2/org/ow2/asm/asm-test/%{version}/asm-test-%{version}.pom
Source6:        https://repo1.maven.org/maven2/org/ow2/asm/asm-tree/%{version}/asm-tree-%{version}.pom
Source7:        https://repo1.maven.org/maven2/org/ow2/asm/asm-util/%{version}/asm-util-%{version}.pom
# We still want to create an "all" uberjar, so this is a custom pom to generate it
# TODO: Fix other packages to no longer depend on "asm-all" so we can drop this
Source8:        asm-all.pom
# The source contains binary jars that cannot be verified for licensing and could be proprietary
Source9:       generate-tarball.sh

# Revert upstream change https://gitlab.ow2.org/asm/asm/-/commit/2a58bc9bcf2ea6eee03e973d1df4cf9312573c9d
# To restore some deprecations that were deleted and broke the API
Patch0: 0001-Revert-upstream-change-2a58bc9.patch

BuildRequires:  maven-local
BuildRequires:  mvn(org.apache.felix:maven-bundle-plugin)
BuildRequires:  mvn(org.apache.maven.plugins:maven-shade-plugin)
BuildRequires:  mvn(org.ow2:ow2:pom:)
%if %{with junit5}
BuildRequires:  mvn(org.codehaus.janino:janino)
BuildRequires:  mvn(org.junit.jupiter:junit-jupiter-api)
BuildRequires:  mvn(org.junit.jupiter:junit-jupiter-engine)
BuildRequires:  mvn(org.junit.jupiter:junit-jupiter-params)
BuildRequires:  mvn(org.apache.maven.surefire:surefire-junit-platform)
%endif

%if %{with osgi}
# asm-all needs to be in pluginpath for BND.  If this self-dependency
# becomes a problem then ASM core will have to be build from source
# with javac before main maven build, just like bnd-module-plugin
BuildRequires:  objectweb-asm >= 6
%endif

# Explicit javapackages-tools requires since asm-processor script uses
# /usr/share/java-utils/java-functions
Requires:       javapackages-tools

%description
ASM is an all purpose Java bytecode manipulation and analysis
framework.  It can be used to modify existing classes or dynamically
generate classes, directly in binary form.  Provided common
transformations and analysis algorithms allow to easily assemble
custom complex transformations and code analysis tools.

%package        javadoc
Summary:        API documentation for %{name}

%description    javadoc
This package provides %{summary}.

%prep
%setup -q

%patch0 -p1

# A custom parent pom to aggregate the build
cp -p %{SOURCE1} pom.xml

%if %{without junit5}
%pom_disable_module asm-test
%endif

# Insert poms into modules
for pom in asm asm-analysis asm-commons asm-test asm-tree asm-util; do
  cp -p $RPM_SOURCE_DIR/${pom}-%{version}.pom $pom/pom.xml
  # Fix junit5 configuration
%if %{with junit5}
  %pom_add_dep org.junit.jupiter:junit-jupiter-engine:5.1.0:test $pom
  %pom_add_plugin org.apache.maven.plugins:maven-surefire-plugin:2.22.0 $pom
%endif
%if %{with osgi}
  if [ "$pom" != "asm-test" ] ; then
    # Make into OSGi bundles
    bsn="org.objectweb.${pom//-/.}"
    %pom_xpath_inject pom:project "<packaging>bundle</packaging>" $pom
    %pom_add_plugin org.apache.felix:maven-bundle-plugin:3.5.0 $pom \
"   <extensions>true</extensions>
    <configuration>
      <instructions>
        <Bundle-SymbolicName>$bsn</Bundle-SymbolicName>
        <Bundle-RequiredExecutionEnvironment>JavaSE-1.8</Bundle-RequiredExecutionEnvironment>
        <_removeheaders>Bnd-LastModified,Build-By,Created-By,Include-Resource,Require-Capability,Tool</_removeheaders>
        <_pluginpath>$(pwd)/tools/bnd-module-plugin/bnd-module-plugin.jar, $(find-jar objectweb-asm/asm-all)</_pluginpath>
        <_plugin>org.objectweb.asm.tools.ModuleInfoBndPlugin;</_plugin>
      </instructions>
    </configuration>"
  fi
%endif
done

# Disable tests that use unlicensed class files
sed -i -e '/testToByteArray_computeMaxs_largeSubroutines/i@org.junit.jupiter.api.Disabled("missing class file")' \
  asm/src/test/java/org/objectweb/asm/ClassWriterTest.java
sed -i -e '/testAnalyze_mergeWithJsrReachableFromTwoDifferentPaths/i@org.junit.jupiter.api.Disabled("missing class file")' \
  asm-analysis/src/test/java/org/objectweb/asm/tree/analysis/AnalyzerWithBasicInterpreterTest.java
sed -i -e '/testAllMethods_issue317586()/i@org.junit.jupiter.api.Disabled("missing class file")' \
  asm-commons/src/test/java/org/objectweb/asm/commons/LocalVariablesSorterTest.java

# Remove failing test SerialVersionUidAdderTest due to missing class files
rm asm-commons/src/test/java/org/objectweb/asm/commons/SerialVersionUidAdderTest.java

# Insert asm-all pom
mkdir -p asm-all
sed 's/@VERSION@/%{version}/g' %{SOURCE8} > asm-all/pom.xml

# Remove invalid self-dependency
%pom_remove_dep org.ow2.asm:asm-test asm-test

# Compat aliases
%mvn_alias :asm-all org.ow2.asm:asm-debug-all

# No need to ship the custom parent pom
%mvn_package :asm-aggregator __noinstall
# Don't ship the test framework to avoid runtime dep on junit
%mvn_package :asm-test __noinstall

%build
# Must compile bnd plugin first, which is used to generate Java 9 module-info.class files
pushd tools/bnd-module-plugin
javac -sourcepath ../../asm/src/main/java/ -cp $(build-classpath aqute-bnd) $(find -name *.java)
jar cf bnd-module-plugin.jar -C src/main/java org
popd

%if %{with junit5}
%mvn_build -- -Dmaven.compiler.source=1.8 -Dmaven.compiler.target=1.8
%else
%mvn_build -f -- -Dmaven.compiler.source=1.8 -Dmaven.compiler.target=1.8
%endif

%install
%mvn_install

%jpackage_script org.objectweb.asm.xml.Processor "" "" %{name}/asm:%{name}/asm-attrs:%{name}/asm-util %{name}-processor true

%files -f .mfiles
%license LICENSE.txt
%{_bindir}/%{name}-processor

%files javadoc -f .mfiles-javadoc
%license LICENSE.txt

%changelog
* Sat Jul 11 2020 Jiri Vanek <jvanek@redhat.com> - 7.3.1-3
- Rebuilt for JDK-11, see https://fedoraproject.org/wiki/Changes/Java11

* Wed May 06 2020 Mat Booth <mat.booth@redhat.com> - 7.3.1-2
- Revert an upstream change to prevent breaking API change

* Thu Feb 27 2020 Jayashree Huttanagoudat <jhuttana@redhat.com> - 7.3.1-1
- Upgraded to upstream version 7.3.1.

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 7.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 7.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 7.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Wed Nov 21 2018 Severin Gehwolf <sgehwolf@redhat.com> - 7.0-1
- Update to latest upstream 7.0 release.
- Removes package asm-xml (deprecated since 6.1).

* Tue Sep 11 2018 Mat Booth <mat.booth@redhat.com> - 6.2.1-1
- Update to latest upstream release
- Fix test suite execution

* Fri Aug 03 2018 Michael Simacek <msimacek@redhat.com> - 6.2-5
- Repack the tarball without binaries

* Wed Aug 01 2018 Severin Gehwolf <sgehwolf@redhat.com> - 6.2-4
- Explicitly require javapackages-tools for asm-processor script
  which uses java-functions.

* Wed Aug 01 2018 Severin Gehwolf <sgehwolf@redhat.com> - 6.2-3
- Allow conditionally building without OSGi
  metadata.

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 6.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Mon Jul 02 2018 Michael Simacek <msimacek@redhat.com> - 6.2-1
- Update to upstream version 6.2

* Sat Jun 30 2018 Mikolaj Izdebski <mizdebsk@redhat.com> - 6.1.1-4
- Relax versioned self-build-requirement a bit

* Fri Jun 29 2018 Mikolaj Izdebski <mizdebsk@redhat.com> - 6.1.1-3
- Add objectweb-asm to BND pluginpath

* Thu Jun 28 2018 Mikolaj Izdebski <mizdebsk@redhat.com> - 6.1.1-2
- Allow conditionally building without junit5

* Wed Apr 25 2018 Mat Booth <mat.booth@redhat.com> - 6.1.1-1
- Update to latest upstream relase for Java 10 support
- Switch to maven build
- Now executing test suites

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 6.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Mon Sep 25 2017 Michael Simacek <msimacek@redhat.com> - 6.0-1
- Update to upstream version 6.0

* Tue Sep 12 2017 Mikolaj Izdebski <mizdebsk@redhat.com> - 6.0-0.2.beta
- Fix invalid OSGi metadata
- Resolves: rhbz#1490817

* Mon Sep 11 2017 Mikolaj Izdebski <mizdebsk@redhat.com> - 6.0-0.1.beta
- Update to upstream version 6.0 beta

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 5.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 5.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Mon Oct 10 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.1-6
- Use OSGi API JARs to run BND classpath, instead of Eclipse

* Sat Sep 24 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.1-5
- Update to current packaging guidelines
- Remove obsoletes and provides for objectweb-asm4

* Wed Jun 15 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.1-4
- Add missing build-requires

* Wed Jun  1 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.1-3
- Avoid calling XMvn from build-classpath

* Tue May 31 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.1-2
- Add missing JARs to BND classpath

* Thu Mar 24 2016 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.1-1
- Update to upstream version 5.1

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 5.0.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Thu Aug 06 2015 Michael Simacek <msimacek@redhat.com> - 5.0.4-1
- Update to upstream version 5.0.4

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 5.0.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sun Jul 20 2014 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.0.3-1
- Update to upstream version 5.0.3

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 5.0.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Mon May  5 2014 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.0.2-1
- Update to upstream version 5.0.2

* Mon Apr 14 2014 Mat Booth <mat.booth@redhat.com> - 5.0.1-2
- SCL-ize package.
- Fix bogus dates in changelog.

* Mon Mar 24 2014 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.0.1-1
- Update to upstream version 5.0.1

* Wed Mar 19 2014 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.0-0.3.beta
- Enable asm-debug-all module

* Mon Jan 20 2014 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.0-0.2.beta
- Remove Eclipse Orbit alias

* Tue Dec  3 2013 Mikolaj Izdebski <mizdebsk@redhat.com> - 5.0-0.1.beta
- Update to 5.0 beta

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:3.3.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Wed Mar  6 2013 Mikolaj Izdebski <mizdebsk@redhat.com> - 0:3.3.1-7
- Make jetty orbit depmap point to asm-all jar
- Resolves: rhbz#917625

* Mon Mar  4 2013 Mikolaj Izdebski <mizdebsk@redhat.com> - 0:3.3.1-6
- Add depmap for org.eclipse.jetty.orbit
- Resolves: rhbz#917625

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:3.3.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Jul 20 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:3.3.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:3.3.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Fri Sep 16 2011 Alexander Kurtakov <akurtako@redhat.com> 0:3.3.1-2
- Use poms produced by the build not foreign ones.
- Adpat to current guidelines.

* Mon Apr 04 2011 Chris Aniszczyk <zx@redhat.com> 0:3.3.1
- Upgrade to 3.3.1

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:3.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Tue Jul 13 2010 Orion Poplawski <orion@cora.nwra.com>  0:3.2.1-2
- Change depmap parent id to asm (bug #606659)

* Thu Apr 15 2010 Fernando Nasser <fnasser@redhat.com> 0:3.2.1
- Upgrade to 3.2

* Sat Jul 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:3.1-7.1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Wed Feb 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:3.1-6.1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Thu Oct 23 2008 David Walluck <dwalluck@redhat.com> 0:3.1-5.1
- build for Fedora

* Thu Oct 23 2008 David Walluck <dwalluck@redhat.com> 0:3.1-5
- add OSGi manifest (Alexander Kurtakov)

* Mon Oct 20 2008 David Walluck <dwalluck@redhat.com> 0:3.1-4
- remove Class-Path from MANIFEST.MF
- add unversioned javadoc symlink
- remove javadoc scriptlets
- fix directory ownership
- remove build requirement on dos2unix

* Fri Feb 08 2008 Ralph Apel <r.apel@r-apel.de> - 0:3.1-3jpp
- Add poms and depmap frags with groupId of org.objectweb.asm !
- Add asm-all.jar 
- Add -javadoc Requires post and postun
- Restore Vendor, Distribution

* Thu Nov 22 2007 Fernando Nasser <fnasser@redhat.com> - 0:3.1-2jpp
- Fix EOL of txt files
- Add dependency on jaxp 

* Thu Nov 22 2007 Fernando Nasser <fnasser@redhat.com> - 0:3.1-1jpp
- Upgrade to 3.1

* Wed Aug 22 2007 Fernando Nasser <fnasser@redhat.com> - 0:3.0-1jpp
- Upgrade to 3.0
- Rename to include objectweb- prefix as requested by ObjectWeb

* Thu Jan 05 2006 Fernando Nasser <fnasser@redhat.com> - 0:2.1-2jpp
- First JPP 1.7 build

* Thu Oct 06 2005 Ralph Apel <r.apel at r-apel.de> 0:2.1-1jpp
- Upgrade to 2.1

* Fri Mar 11 2005 Sebastiano Vigna <vigna at acm.org> 0:2.0.RC1-1jpp
- First release of the 2.0 line.